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
    """Scrape the jail roster and return inmate data with detail page info"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        print("Fetching jail table...")
        response = requests.get(JAIL_URL, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        tables = soup.find_all('table')
        if not tables:
            print("No tables found on the page")
            return []

        for table in tables:
            header_row = table.find('tr')
            if not header_row:
                continue
            headers_list = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            expected_headers = ['Name', 'Sex', 'Height', 'Weight', 'Eye Color', 'Hair Color', 'Booking Date']
            if not all(header in headers_list for header in expected_headers):
                continue

            rows = table.find_all('tr')[1:]  # Skip header row
            inmates = []
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                if len(cells) < 7:
                    continue
                try:
                    name = cells[0].strip()
                    sex = cells[1].strip()
                    height = cells[2].strip()
                    weight = cells[3].strip()
                    eye_color = cells[4].strip()
                    hair_color = cells[5].strip()
                    booking_date = cells[6].strip()
                    # Extract jailid from onclick attribute of <tr>
                    jailid = None
                    onclick_attr = row.get('onclick', '')
                    jailid_match = re.search(r'jailid=(\d{6})', onclick_attr)
                    if jailid_match:
                        jailid = jailid_match.group(1)
                    # Construct detail link using jailid
                    detail_link = None
                    if jailid:
                        detail_link = f'https://www.angelinacounty.net/injail/inmate/?jailid={jailid}'
                    if (name and len(name) > 3 and 
                        sex in ['Male', 'Female'] and
                        booking_date and '/' in booking_date):
                        try:
                            booking_datetime = datetime.strptime(booking_date, '%m/%d/%Y')
                        except ValueError:
                            continue
                        # Scrape detail page if available
                        mugshot_url = None
                        aliases = []
                        tattoos = []
                        demographics = None
                        offenses = []
                        if detail_link:
                            try:
                                detail_resp = requests.get(detail_link, headers=headers, timeout=20)
                                detail_resp.raise_for_status()
                                detail_soup = BeautifulSoup(detail_resp.content, 'html.parser')
                                # Mugshots
                                mugshot_url = None
                                inmate_image_div = detail_soup.find('div', class_='inmate-image')
                                if inmate_image_div:
                                    img_tag = inmate_image_div.find('img')
                                    if img_tag and img_tag.get('src'):
                                        mugshot_url = img_tag['src']
                                        if not mugshot_url.startswith('http'):
                                            mugshot_url = 'https://www.angelinacounty.net' + mugshot_url
                                print(f"Mugshot URL for {name}: {mugshot_url}")
                                # Demographics
                                demographics = {}
                                details_div = detail_soup.find('div', class_='inmate-details')
                                if details_div:
                                    p_tag = details_div.find('p')
                                    if p_tag:
                                        for line in p_tag.decode_contents().split('<br>'):
                                            line = BeautifulSoup(line, 'html.parser').get_text().strip()
                                            if ':' in line:
                                                k, v = line.split(':', 1)
                                                demographics[k.strip().lower().replace(' ', '_')] = v.strip()
                                print(f"Demographics for {name}: {demographics}")
                                # Offenses
                                offenses = []
                                offense_table = detail_soup.find('table', class_='table-mobile-full')
                                if offense_table:
                                    rows = offense_table.find_all('tr')
                                    for tr in rows[1:]:  # skip header
                                        tds = tr.find_all('td')
                                        if len(tds) == 5:
                                            offense = {
                                                'charge': tds[0].get_text(strip=True),
                                                'degree': tds[1].get_text(strip=True),
                                                'bond': tds[2].get_text(strip=True),
                                                'hold_reason': tds[3].get_text(strip=True),
                                                'agency': tds[4].get_text(strip=True)
                                            }
                                            offenses.append(offense)
                                print(f"Offenses for {name}: {offenses}")
                                # Aliases
                                aliases = []
                                alias_box = detail_soup.find('div', class_='box-content', text=None)
                                if alias_box:
                                    alias_title = alias_box.find('h6', string=re.compile('Known Aliases'))
                                    if alias_title:
                                        ul = alias_box.find('ul')
                                        if ul:
                                            aliases = [li.get_text(strip=True) for li in ul.find_all('li')]
                                print(f"Aliases for {name}: {aliases}")
                                # Tattoos/Scars/Marks
                                tattoos = []
                                tattoo_box = None
                                for box in detail_soup.find_all('div', class_='box-content'):
                                    title = box.find('h6')
                                    if title and 'Scars/Marks/Tattoos' in title.get_text():
                                        tattoo_box = box
                                        break
                                if tattoo_box:
                                    ul = tattoo_box.find('ul')
                                    if ul:
                                        tattoos = [li.get_text(strip=True) for li in ul.find_all('li')]
                                print(f"Tattoos for {name}: {tattoos}")
                            except Exception as e:
                                print(f"Error scraping detail page for {name}: {e}")
                        print(f"\n--- Detail for {name} ---")
                        print(f"Aliases: {aliases}")
                        print(f"Tattoos: {tattoos}")
                        print(f"Demographics: {demographics}")
                        print(f"Offenses: {offenses}")
                        inmate = {
                            'name': name,
                            'sex': sex,
                            'height': height,
                            'weight': weight,
                            'eye_color': eye_color,
                            'hair_color': hair_color,
                            'booking_date': booking_date,
                            'booking_datetime': booking_datetime,
                            'detail_link': detail_link,
                            'mugshot_url': mugshot_url,
                            'aliases': aliases,
                            'tattoos': tattoos,
                            'demographics': demographics,
                            'offenses': offenses
                        }
                        inmates.append(inmate)
                except Exception as e:
                    print(f"Error parsing row: {cells} - {e}")
                    continue
            if inmates:
                inmates.sort(key=lambda x: x['booking_datetime'], reverse=True)
                return inmates
        return []
    except requests.RequestException as e:
        print(f"Error fetching jail data: {e}")
        return []
    except Exception as e:
        print(f"Error parsing jail data: {e}")
        return []

def generate_rss(inmates):
    """Generate RSS feed from inmate data with detail info"""
    if not inmates:
        print("No inmates to include in RSS feed")
        return None
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = 'Angelina County Jail Roster'
    ET.SubElement(channel, 'link').text = JAIL_URL
    ET.SubElement(channel, 'description').text = 'Recent bookings at Angelina County Jail'
    ET.SubElement(channel, 'language').text = 'en-us'
    ET.SubElement(channel, 'lastBuildDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
    for inmate in inmates[:50]:
        item = ET.SubElement(channel, 'item')
        title = f"{inmate['name']} - {inmate['booking_date']}"
        ET.SubElement(item, 'title').text = title
        ET.SubElement(item, 'link').text = inmate.get('detail_link', JAIL_URL)
        desc_lines = [
            f"<b>Name:</b> {inmate['name']}",
            f"<b>Sex:</b> {inmate['sex']}",
            f"<b>Height:</b> {inmate['height']}",
            f"<b>Weight:</b> {inmate['weight']}",
            f"<b>Eye Color:</b> {inmate['eye_color']}",
            f"<b>Hair Color:</b> {inmate['hair_color']}",
            f"<b>Booking Date:</b> {inmate['booking_date']}"
        ]
        if inmate.get('mugshot_url'):
            desc_lines.append(f'<img src="{inmate["mugshot_url"]}" alt="Mugshot" width="150"/>')
        else:
            desc_lines.append('<i>No mugshot available</i>')
        if inmate.get('aliases'):
            desc_lines.append('<b>Known Aliases:</b> ' + ', '.join(inmate['aliases']))
        if inmate.get('tattoos'):
            desc_lines.append('<b>Scars/Marks/Tattoos:</b> ' + ', '.join(inmate['tattoos']))
        demo = inmate.get('demographics')
        if isinstance(demo, dict) and demo:
            demo_str = ', '.join([f'{k.capitalize()}: {v}' for k, v in demo.items()])
            desc_lines.append('<b>Demographics:</b> ' + demo_str)
        if inmate.get('offenses'):
            desc_lines.append('<b>Offenses:</b><ul>')
            for off in inmate['offenses']:
                desc_lines.append(f'<li>{off["charge"]} ({off["degree"]}) - Bond: {off["bond"]}, Hold: {off["hold_reason"]}, Agency: {off["agency"]}</li>')
            desc_lines.append('</ul>')
        description = '<br/>'.join(desc_lines)
        ET.SubElement(item, 'description').text = description.strip()
        pub_datetime = inmate['booking_datetime'].replace(hour=12, minute=0, second=0)
        pub_date = pub_datetime.strftime('%a, %d %b %Y %H:%M:%S +0000')
        ET.SubElement(item, 'pubDate').text = pub_date
        guid = f"angelina-jail-{inmate['name'].replace(' ', '-').replace(',', '')}-{inmate['booking_date'].replace('/', '-')}"
        ET.SubElement(item, 'guid', isPermaLink='false').text = guid
    return rss

def main():
    print("Starting RSS generation...")
    inmates = get_jail_table()
    if inmates:
        print(f"Successfully found {len(inmates)} inmates")
        rss_feed = generate_rss(inmates)
        if rss_feed:
            rough_string = ET.tostring(rss_feed, 'unicode')
            reparsed = minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent="  ")
            pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
            output_path = os.path.join('docs', 'angelina_jail_feed.xml')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(pretty_xml)
            print("RSS feed generated successfully!")
            print(f"Feed contains {len(inmates[:50])} recent bookings")
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