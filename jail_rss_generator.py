#!/usr/bin/env python3

import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from bs4 import BeautifulSoup
from datetime import datetime
import re
import os

# Configuration
JAIL_URL = "https://www.angelinacounty.net/injail/"

def get_jail_table():
    """Scrape the jail roster and return inmate data"""
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        print("Fetching jail table...")
        response = requests.get(JAIL_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Debug information
        print("=== DEBUG: Page Analysis ===")
        print(f"Page title: {soup.title.string if soup.title else 'No title'}")
        
        tables = soup.find_all('table')
        print(f"Found {len(tables)} table(s)")
        
        if not tables:
            print("No tables found on the page")
            return []
        
        # Analyze each table
        for i, table in enumerate(tables, 1):
            print(f"Analyzing table {i}:")
            
            # Get headers
            header_row = table.find('tr')
            if not header_row:
                print(f"  - No header row found")
                continue
                
            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            print(f"  - Headers: {headers}")
            
            # Check if this looks like the jail table
            expected_headers = ['Name', 'Sex', 'Height', 'Weight', 'Eye Color', 'Hair Color', 'Booking Date']
            if not all(header in headers for header in expected_headers):
                print(f"  - Not the jail table (missing expected headers)")
                continue
            
            # Get all rows except header
            rows = table.find_all('tr')[1:]  # Skip header row
            print(f"  - Has {len(rows)} data rows")
            
            if len(rows) < 5:
                print(f"  - Too few rows, showing all:")
                for j, row in enumerate(rows, 1):
                    cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                    print(f"    Row {j}: {cells}")
            else:
                print(f"  - Showing first 5 rows:")
                for j, row in enumerate(rows[:5], 1):
                    cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                    print(f"    Row {j}: {cells}")
            
            # Process inmates from this table
            inmates = []
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                
                # Skip empty rows or rows with insufficient data
                if len(cells) < 7:
                    continue
                
                # Extract inmate data - adjust indices based on your headers
                try:
                    name = cells[0].strip()
                    sex = cells[1].strip()
                    height = cells[2].strip()
                    weight = cells[3].strip()
                    eye_color = cells[4].strip()
                    hair_color = cells[5].strip()
                    booking_date = cells[6].strip()
                    
                    # Validate that this looks like real inmate data
                    if (name and len(name) > 3 and 
                        sex in ['Male', 'Female'] and
                        booking_date and '/' in booking_date):
                        
                        # Parse booking date
                        try:
                            booking_datetime = datetime.strptime(booking_date, '%m/%d/%Y')
                        except ValueError:
                            print(f"    Skipping {name} - invalid date format: {booking_date}")
                            continue
                        
                        inmate = {
                            'name': name,
                            'sex': sex,
                            'height': height,
                            'weight': weight,
                            'eye_color': eye_color,
                            'hair_color': hair_color,
                            'booking_date': booking_date,
                            'booking_datetime': booking_datetime
                        }
                        inmates.append(inmate)
                        
                except (IndexError, ValueError) as e:
                    print(f"    Error parsing row: {cells} - {e}")
                    continue
            
            print(f"=== Found {len(inmates)} inmates ===")
            
            if inmates:
                # Sort by booking date (newest first)
                inmates.sort(key=lambda x: x['booking_datetime'], reverse=True)
                
                print("Recent bookings:")
                for inmate in inmates[:5]:
                    print(f"  - {inmate['name']} ({inmate['booking_date']})")
                
                return inmates
            else:
                print("No valid inmate records found in table")
        
        print("No jail table found with expected structure")
        return []
        
    except requests.RequestException as e:
        print(f"Error fetching jail data: {e}")
        return []
    except Exception as e:
        print(f"Error parsing jail data: {e}")
        return []

def generate_rss(inmates):
    """Generate RSS feed from inmate data"""
    
    if not inmates:
        print("No inmates to include in RSS feed")
        return None
    
    # Create RSS feed
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    
    # Channel metadata
    ET.SubElement(channel, 'title').text = 'Angelina County Jail Roster'
    ET.SubElement(channel, 'link').text = JAIL_URL
    ET.SubElement(channel, 'description').text = 'Recent bookings at Angelina County Jail'
    ET.SubElement(channel, 'language').text = 'en-us'
    ET.SubElement(channel, 'lastBuildDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
    
    # Add items for recent bookings (last 50)
    for inmate in inmates[:50]:
        item = ET.SubElement(channel, 'item')
        
        title = f"{inmate['name']} - {inmate['booking_date']}"
        ET.SubElement(item, 'title').text = title
        ET.SubElement(item, 'link').text = JAIL_URL
        
        description = f"""
        <b>Name:</b> {inmate['name']}<br/>
        <b>Sex:</b> {inmate['sex']}<br/>
        <b>Height:</b> {inmate['height']}<br/>
        <b>Weight:</b> {inmate['weight']}<br/>
        <b>Eye Color:</b> {inmate['eye_color']}<br/>
        <b>Hair Color:</b> {inmate['hair_color']}<br/>
        <b>Booking Date:</b> {inmate['booking_date']}
        """
        ET.SubElement(item, 'description').text = description.strip()
        
        # Use booking date as publication date (set to noon for consistency)
        pub_datetime = inmate['booking_datetime'].replace(hour=12, minute=0, second=0)
        pub_date = pub_datetime.strftime('%a, %d %b %Y %H:%M:%S +0000')
        ET.SubElement(item, 'pubDate').text = pub_date
        
        # Create unique ID for this booking
        guid = f"angelina-jail-{inmate['name'].replace(' ', '-').replace(',', '')}-{inmate['booking_date'].replace('/', '-')}"
        ET.SubElement(item, 'guid', isPermaLink='false').text = guid
    
    return rss

def main():
    """Main function to generate RSS feed"""
    print("Starting RSS generation...")
    
    inmates = get_jail_table()
    
    if inmates:
        print(f"Successfully found {len(inmates)} inmates")
        
        rss_feed = generate_rss(inmates)
        
        if rss_feed:
            # Pretty print the XML
            rough_string = ET.tostring(rss_feed, 'unicode')
            reparsed = minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent="  ")
            
            # Remove extra blank lines
            pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
            
            # Write to file
            with open('angelina_jail_feed.xml', 'w', encoding='utf-8') as f:
                f.write(pretty_xml)
            
            print("RSS feed generated successfully!")
            print(f"Feed contains {len(inmates[:50])} recent bookings")
            
            # Output some stats
            print("\n=== RSS Feed Stats ===")
            print(f"Total inmates found: {len(inmates)}")
            print(f"Recent bookings (last 7 days): {len([i for i in inmates if (datetime.now() - i['booking_datetime']).days <= 7])}")
            print(f"Most recent booking: {inmates[0]['name']} on {inmates[0]['booking_date']}")
            
        else:
            print("Failed to generate RSS feed.")
            return False
    else:
        print("No inmate data found - RSS feed not generated")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("Python script completed with errors")
        exit(1)
    else:
        print("Python script completed successfully")