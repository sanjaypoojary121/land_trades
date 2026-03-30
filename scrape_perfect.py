import requests
from bs4 import BeautifulSoup
import json
import time
import re

class LandtradesScraper:
    def __init__(self):
        self.base_url = "https://landtrades.in"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.projects_data = {}
        
        # Project name mapping
        self.project_mapping = {
            "altitude-residential-project-bendoorwell": "Altitude",
            "expertise-enclave-apartment-in-mangalore": "Expertise Enclave",
            "durga-mahal-apartment-in-mannaguda-road-kudroli": "Durga Mahal",
            "laxmi-govind-apartment-in-kadri-mangalore": "Laxmi Govind",
            "krishna-kuteera-apartment-in-mangalore": "Krishna Kuteera",
            "mahalaxmi-residential-apartment-mangalore": "Mahalaxmi",
            "sky-villa-apartments-mangalore": "BMK Sky Villa",
            "pristine-flats-mangalore": "Pristine",
            "shivabagh-residential-apartment-mangalore": "Shivabagh",
            "altura-residential-bendoorwell-mangalore": "Altura",
            "vikram-commercial-complex-kodialbail-mangalore": "Vikram",
            "synergy-commercial-project-mangalore": "Synergy",
        }

    def get_project_name_from_url(self, url):
        """Extract project name from URL"""
        slug = url.split('/')[-1].replace('.php', '')
        return self.project_mapping.get(slug, slug.replace('-', ' ').title())

    def extract_highlights(self, soup):
        """Extract highlights from h3 tags in project details"""
        highlights = []
        try:
            h3_tags = soup.find_all('h3')
            known_keys = ['Typology', 'Location', 'Price', 'Project Size', 'Possession Date', 
                         'Status', 'Unit Type', 'Project Area', 'RERA']
            
            for h3 in h3_tags:
                text = h3.get_text(strip=True)
                
                # Skip if it's a section header (like "Floor Plans", "3D Floor Plan")
                if 'Floor' in text or 'plan' in text.lower():
                    continue
                
                # Check if this h3 contains a known key
                for key in known_keys:
                    if key.lower() in text.lower():
                        # Extract key and value
                        idx = text.lower().find(key.lower())
                        key_text = text[:idx + len(key)].strip()
                        value_text = text[idx + len(key):].strip()
                        
                        if value_text:
                            highlight = f"{key_text}: {value_text}"
                            if highlight not in highlights:
                                highlights.append(highlight)
                        break
            
            return highlights
        except Exception as e:
            print(f"Error extracting highlights: {e}")
            return highlights

    def extract_floor_plans(self, soup):
        """Extract floor plans from project-plans-bg section only"""
        floor_plans = []
        try:
            # Find the floor plans section
            plans_section = soup.find('section', class_='project-plans-bg')
            if not plans_section:
                return floor_plans
            
            # Get h3 and h4 ONLY from this section
            h3_tags = plans_section.find_all('h3')
            h4_tags = plans_section.find_all('h4')
            
            # Match h3 types with h4 names by parsing structure
            # Based on analysis: 
            # H3[0]: "Typical Floor Plan" -> H4[0]: "Typical Unit Plan"
            # H3[1]: "3D Floor Plan" -> H4[1,2,3]: "BASEMENT...", "UPPER...", "AMENITIES..."
            # H3[2]: "Terrace Plan" -> H4[4]: "Terrace Floor Plan"
            
            h4_index = 0
            
            for h3_index, h3 in enumerate(h3_tags):
                h3_text = h3.get_text(strip=True)
                
                # Determine how many h4s belong to this h3
                if h3_index == 0:  # "Typical Floor Plan"
                    # Gets 1 h4
                    h4_count = 1
                elif h3_index == 1:  # "3D Floor Plan"
                    # Gets 3 h4s (BASEMENT, UPPER, AMENITIES)
                    h4_count = 3
                elif h3_index == 2:  # "Terrace Plan"
                    # Gets remaining h4s (usually 1: Terrace Floor Plan)
                    h4_count = len(h4_tags) - h4_index
                else:
                    # Default: 1 h4 per h3
                    h4_count = 1
                
                # Collect h4s for this h3
                for _ in range(h4_count):
                    if h4_index < len(h4_tags):
                        h4_text = h4_tags[h4_index].get_text(strip=True)
                        formatted = f"{h3_text}: {h4_text}"
                        if formatted not in floor_plans:
                            floor_plans.append(formatted)
                        h4_index += 1
            
            return floor_plans
        except Exception as e:
            print(f"Error extracting floor plans: {e}")
            return floor_plans

    def extract_amenities(self, soup):
        """Extract amenities"""
        amenities = []
        try:
            amenities_section = soup.find('section', class_='project-amenities-bg')
            
            if amenities_section:
                text = amenities_section.get_text()
                lines = text.split('\n')
                
                started = False
                for line in lines:
                    line_clean = line.strip()
                    
                    if 'Amenities' in line_clean and not started:
                        started = True
                        continue
                    
                    if started and line_clean and len(line_clean) > 3:
                        if any(x in line_clean.lower() for x in ['floor plan', 'location', 'faq', 'specification']):
                            break
                        
                        if not any(x in line_clean.lower() for x in ['select', 'email', 'phone', 'click', 'button', 'search']):
                            if line_clean not in amenities:
                                amenities.append(line_clean)
            
            return amenities
        except Exception as e:
            print(f"Error extracting amenities: {e}")
            return amenities

    def extract_connectivity(self, soup):
        """Extract connectivity - distance and location pairs"""
        connectivity = []
        try:
            all_text = soup.get_text()
            lines = all_text.split('\n')
            
            # Find Connectivity section
            connectivity_start = -1
            for i, line in enumerate(lines):
                if 'Connectivity' in line:
                    connectivity_start = i
                    break
            
            if connectivity_start < 0:
                return connectivity
            
            # Extract distance-location pairs
            i = connectivity_start + 1
            while i < len(lines):
                line = lines[i].strip()
                
                # Look for distance pattern
                if re.match(r'^\d+\.?\d*\s*(km|kms|mtrs|meters|miles)', line, re.IGNORECASE):
                    # Get the next non-empty line as location
                    location_found = False
                    for j in range(i+1, min(i+5, len(lines))):
                        next_line = lines[j].strip()
                        if next_line and len(next_line) > 2 and not re.match(r'^\d', next_line):
                            combined = f"{line}: {next_line}"
                            if combined not in connectivity and len(next_line) < 100:
                                connectivity.append(combined)
                            location_found = True
                            break
                    
                    if location_found:
                        i = j
                        continue
                
                # Exit if we've hit another major section
                if any(x in line.lower() for x in ['faq', 'specification', 'highlight', 'document']) and i > connectivity_start + 10:
                    break
                
                i += 1
            
            return connectivity
        except Exception as e:
            print(f"Error extracting connectivity: {e}")
            return connectivity

    def extract_faq(self, soup):
        """Extract FAQ from card elements and accordion structures"""
        faq = []
        try:
            # Method 1: Find all card divs (both collapsed and expanded)
            cards = soup.find_all('div', class_='card')
            
            for card in cards:
                # Try to find header with class card-header
                header = card.find('div', class_='card-header')
                body = card.find('div', class_='card-body')
                
                if header and body:
                    question = header.get_text(strip=True).replace('×', '').strip()
                    answer = body.get_text(strip=True)
                    
                    if question and answer:
                        faq_text = f"{question} {answer}"
                        if faq_text not in faq:
                            faq.append(faq_text)
            
            # Method 2: Search page text for FAQ-like patterns
            if len(faq) < 3:  # If we didn't get many FAQs, try text search
                all_text = soup.get_text()
                lines = all_text.split('\n')
                
                in_faq_section = False
                for i, line in enumerate(lines):
                    line_clean = line.strip()
                    
                    if "FAQ" in line_clean:
                        in_faq_section = True
                        continue
                    
                    if in_faq_section and re.match(r'^\d+\.\s+', line_clean):
                        # This looks like a numbered FAQ
                        question = line_clean
                        # Try to find the answer on next lines
                        answer_lines = []
                        for j in range(i+1, min(i+5, len(lines))):
                            next_line = lines[j].strip()
                            if next_line and not re.match(r'^\d+\.\s+', next_line):
                                answer_lines.append(next_line)
                            elif re.match(r'^\d+\.\s+', next_line):
                                break
                        
                        if answer_lines:
                            answer = ' '.join(answer_lines)
                            faq_text = f"{question} {answer}"
                            if faq_text not in faq:
                                faq.append(faq_text)
                    
                    # Exit FAQ section
                    if in_faq_section and any(x in line_clean.lower() for x in ['specification', 'document', 'bank']):
                        in_faq_section = False
            
            return faq
        except Exception as e:
            print(f"Error extracting FAQ: {e}")
            return faq

    def extract_specifications(self, soup):
        """Extract specifications"""
        specs = {}
        try:
            modals = soup.find_all('div', class_='modal-content')
            
            if modals:
                for modal in modals:
                    text = modal.get_text()
                    lines = text.split('\n')
                    
                    current_section = None
                    section_content = []
                    
                    for line in lines:
                        line_clean = line.strip()
                        if not line_clean:
                            continue
                        
                        # Check for section headers
                        if line_clean.isupper() and len(line_clean) < 50 and ' ' in line_clean:
                            if current_section and section_content:
                                specs[current_section] = section_content
                            
                            current_section = line_clean
                            section_content = []
                        elif current_section and line_clean:
                            section_content.append(line_clean)
                    
                    if current_section and section_content:
                        specs[current_section] = section_content
            
            return specs
        except Exception as e:
            print(f"Error extracting specifications: {e}")
            return specs

    def scrape_project(self, url):
        """Scrape a project page"""
        try:
            print(f"Scraping: {url.split('/')[-1]}")
            response = self.session.get(url, timeout=15)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.content, 'html.parser')
            
            project_name = self.get_project_name_from_url(url)
            
            # Extract data
            highlights = self.extract_highlights(soup)
            floor_plans = self.extract_floor_plans(soup)
            amenities = self.extract_amenities(soup)
            connectivity = self.extract_connectivity(soup)
            faq = self.extract_faq(soup)
            specifications = self.extract_specifications(soup)
            
            # Create project data dictionaries
            project_data = {
                "project_name": project_name,
                "url": url,
                "High lights": highlights,
                "Floor Plans": floor_plans,
                "amenities": amenities
            }
            
            project_info = {
                "project_name": project_name,
                "url": url,
                "Connectivity": connectivity,
                "FAQ'S": faq,
                "source": url
            }
            
            project_specs = {
                "project_name": project_name,
                "url": url,
                "source": url
            }
            project_specs.update(specifications)
            
            return project_data, project_info, project_specs
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None, None, None

    def scrape_all_projects(self):
        """Scrape all projects"""
        project_urls = [
            "https://landtrades.in/altitude-residential-project-bendoorwell.php",
            "https://landtrades.in/expertise-enclave-apartment-in-mangalore.php",
            "https://landtrades.in/durga-mahal-apartment-in-mannaguda-road-kudroli.php",
            "https://landtrades.in/laxmi-govind-apartment-in-kadri-mangalore.php",
            "https://landtrades.in/krishna-kuteera-apartment-in-mangalore.php",
            "https://landtrades.in/mahalaxmi-residential-apartment-mangalore.php",
            "https://landtrades.in/sky-villa-apartments-mangalore.php",
            "https://landtrades.in/pristine-flats-mangalore.php",
            "https://landtrades.in/shivabagh-residential-apartment-mangalore.php",
            "https://landtrades.in/altura-residential-bendoorwell-mangalore.php",
            "https://landtrades.in/vikram-commercial-complex-kodialbail-mangalore.php",
            "https://landtrades.in/synergy-commercial-project-mangalore.php",
        ]
        
        for url in project_urls:
            project_data, project_info, project_specs = self.scrape_project(url)
            
            if project_data:
                project_name = project_data['project_name']
                self.projects_data[project_name] = project_data
                self.projects_data[f"{project_name} info"] = project_info
                self.projects_data[f"{project_name} Specifications"] = project_specs
            
            time.sleep(2)
        
        return self.projects_data

    def save_to_json(self, filepath):
        """Save to JSON"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.projects_data, f, ensure_ascii=False, indent=2)
            print(f"\nData saved to {filepath}")
        except Exception as e:
            print(f"Error saving to JSON: {e}")

def main():
    scraper = LandtradesScraper()
    print("Starting Land Trades Scraper (Optimized)...\n")
    
    scraper.scrape_all_projects()
    
    output_path = "landtrades_projects_extracted.json"
    scraper.save_to_json(output_path)
    
    print(f"Total items scraped: {len(scraper.projects_data)}")

if __name__ == "__main__":
    main()
