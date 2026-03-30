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
        info_text = None
        
        try:
            # First, extract Info field from the first significant paragraph (we'll add it LAST)
            info_text = self._extract_info(soup)
            
            h3_tags = soup.find_all('h3')
            known_keys = ['Typology', 'Location', 'Price', 'Project Size', 'Possession Date', 
                         'Status', 'Unit Type', 'Project Area', 'RERA', 'storey', 'floor']
            
            for h3 in h3_tags:
                text = h3.get_text(strip=True)
                
                # Skip if it's a section header (like "Floor Plans", "3D Floor Plan")
                # But ALLOW "Project Size" entries that contain "Floors"
                if ('Floor' in text and 'Project Size' not in text) or 'plan' in text.lower():
                    continue
                
                # Skip if it's "Well-Connected Location" (this shouldn't be in this list)
                if 'Well-Connected' in text or 'intheHeart' in text:
                    continue
                
                # Check for storey/floor patterns and convert to Project Size
                storey_match = re.search(r'(\d+)[\s\-]*(storey|stories|floor|floors)', text, re.IGNORECASE)
                if storey_match:
                    storey_num = storey_match.group(1)
                    unit = 'Floors' if 'floor' in storey_match.group(2).lower() else 'Storey'
                    highlight = f"Project Size: {storey_num} {unit}"
                    if not any(h.startswith("Project Size") for h in highlights):
                        highlights.append(highlight)
                    continue
                
                # Check if this h3 contains a known key
                matched = False
                for key in known_keys:
                    if key.lower() in text.lower() and key not in ['storey', 'floor']:
                        # Extract key and value
                        idx = text.lower().find(key.lower())
                        key_text = text[:idx + len(key)].strip()
                        value_text = text[idx + len(key):].strip()
                        
                        # Handle cases where value starts immediately (no space/separator)
                        # e.g., "Project Size28 Floors" -> extract "28 Floors"
                        if value_text and not value_text[0].isspace() and value_text[0] != ':':
                            # Value is concatenated directly, which is fine
                            pass
                        
                        # Also strip leading colon and spaces
                        value_text = value_text.lstrip(': ')
                        
                        if value_text:
                            # Clean up the value - remove trailing punctuation but keep the content
                            value_text = value_text.strip(', ')
                            
                            # Clean Location formatting (remove extra spaces)
                            if key.lower() == 'location':
                                value_text = ', '.join([v.strip() for v in value_text.split(',')])
                            
                            # Clean up RERA formatting
                            if key.lower() == 'rera':
                                # Extract just the RERA number
                                rera_match = re.search(r'PRM/KA/RERA/\d+/\d+/PR/\d+/\d+', value_text)
                                if rera_match:
                                    value_text = rera_match.group(0)
                                    key_text = "RERA Number"  # No space before colon
                                else:
                                    continue
                            
                            highlight = f"{key_text}: {value_text}"
                            # Check if we already have this key
                            if not any(h.startswith(key_text.strip()) for h in highlights):
                                highlights.append(highlight)
                            matched = True
                        break
            
            # ADD INFO AS THE LAST ITEM
            if info_text:
                # Limit info to full length (don't truncate)
                highlights.append(f"Info: {info_text}")
            
            return highlights
        except Exception as e:
            print(f"Error extracting highlights: {e}")
            return highlights
    
    def _extract_info(self, soup):
        """Extract project info/description"""
        try:
            # Look for the first substantial paragraph after the header
            all_p = soup.find_all('p')
            for p in all_p:
                text = p.get_text(strip=True)
                # Find substantial paragraphs (usually info paragraphs)
                if len(text) > 200 and not text.startswith("₹") and not text.startswith("INR"):
                    return text
            
            # Fallback: look for text in divs with specific classes
            content_divs = soup.find_all('div', class_=re.compile(r'content|description|info|about'))
            for div in content_divs:
                text = div.get_text(strip=True)
                if len(text) > 200:
                    return text
            
            return None
        except Exception as e:
            return None

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
            
            if not h3_tags or not h4_tags:
                return floor_plans
            
            # Build H3 type names (e.g., "Typical Floor Plan", "3D Floor Plan", "Terrace Plan")
            h3_types = [h3.get_text(strip=True) for h3 in h3_tags]
            
            h4_index = 0
            
            for h3_index, h3_type in enumerate(h3_types):
                # Determine how many h4s belong to this h3 based on distribution
                if h3_index == 0:  # First type (usually "Typical Floor Plan")
                    # Usually gets 1-2 h4s
                    h4_count = 1
                elif h3_index == 1:  # Second type (usually "3D Floor Plan")
                    # Usually gets 2-3 h4s, but for some projects might get more
                    # Count remaining and estimate
                    remaining = len(h4_tags) - h4_index
                    if h3_index == len(h3_types) - 1:  # If last H3, take remaining
                        h4_count = remaining
                    else:
                        h4_count = min(3, remaining)  # Default to 3, but adjust if needed
                else:  # Other types ("Terrace Plan", etc.)
                    # Get all remaining
                    h4_count = len(h4_tags) - h4_index
                
                # Collect h4s for this h3
                for _ in range(h4_count):
                    if h4_index < len(h4_tags):
                        h4 = h4_tags[h4_index]
                        h4_text = h4.get_text(strip=True)
                        # Normalize the case
                        h4_normalized = self._normalize_case(h4_text)
                        plan_entry = f"{h3_type}: {h4_normalized}"
                        if plan_entry not in floor_plans:
                            floor_plans.append(plan_entry)
                        h4_index += 1
            
            return floor_plans
        except Exception as e:
            print(f"Error extracting floor plans: {e}")
            return floor_plans
    
    def _normalize_case(self, text):
        """Normalize text case: Title case, remove lowercase 'floor', 'plan'"""
        # Split into words
        words = text.split()
        result = []
        for word in words:
            # Title case: first letter uppercase, rest lowercase
            # But preserve patterns like "2nd", "24th", etc.
            if word and not word[0].isdigit():
                result.append(word[0].upper() + word[1:].lower() if len(word) > 1 else word.upper())
            else:
                result.append(word)
        
        return ' '.join(result)

    def extract_amenities(self, soup):
        """Extract amenities from project-amenities-bg section"""
        amenities = []
        try:
            # Find the main amenities section
            amenities_section = soup.find('section', class_='project-amenities-bg')
            if not amenities_section:
                return self._extract_amenities_from_text(soup)
            
            # Get all text elements in the amenities section
            items = amenities_section.find_all(['h4', 'p', 'li', 'span', 'div'])
            
            for item in items:
                text = item.get_text(strip=True)
                # Filter out empty, short, or non-relevant text
                if text and len(text) > 3 and len(text) < 100:
                    # Skip if it's a section header or form element or uppercase FIELD NAMES
                    skip_words = ['select', 'email', 'phone', 'click', 'button', 'search',
                                 'amenities', 'specification', 'highlights', 'floor', 'plan']
                    if any(word in text.lower() for word in skip_words):
                        continue
                    
                    if text not in amenities and len(text.split()) <= 8:
                        amenities.append(text)
            
            # If original method gave few results, try alternate
            if len(amenities) < 5:
                amenities = self._extract_amenities_from_text(soup)
            
            return amenities[:20]  # Limit to 20 amenities
        except Exception as e:
            print(f"Error extracting amenities: {e}")
            return amenities
    
    def _extract_amenities_from_text(self, soup):
        """Extract amenities from text content when section not found"""
        amenities = []
        try:
            amenities_section = soup.find('section', class_='project-amenities-bg')
            if amenities_section:
                text = amenities_section.get_text()
            else:
                text = soup.get_text()
            
            lines = text.split('\n')
            
            in_amenities = False
            for i, line in enumerate(lines):
                line_clean = line.strip()
                
                if 'Amenities' in line_clean and 'project-amenities' not in line_clean.lower():
                    in_amenities = True
                    continue
                
                if in_amenities:
                    # Stop at next major section
                    if any(x in line_clean.lower() for x in ['floor plan', 'faq', 'specification', 'connectivity', 'highlight']):
                        break
                    
                    # Extract bullet points or list items
                    if line_clean and len(line_clean) > 3 and len(line_clean) < 100:
                        # Remove bullet markers
                        text_clean = line_clean.lstrip('•- ').strip()
                        # Skip form elements and UI text
                        skip_keywords = ['select', 'email', 'phone', 'click', 'button', 'search', 'enter', 'yes', 'no', 'option']
                        if not any(word in text_clean.lower() for word in skip_keywords):
                            # Only skip very short items (1-2 words usually noise)
                            if text_clean and text_clean not in amenities and len(text_clean.split()) >= 2:
                                amenities.append(text_clean)
            
            return amenities
        except Exception as e:
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
        """Extract specifications with proper section detection"""
        specs = {}
        try:
            # Method 1: Try modal content first
            modals = soup.find_all('div', class_='modal-content')
            
            if modals:
                for modal in modals:
                    text = modal.get_text()
                    specs = self._parse_specifications_text(text)
                    if specs:
                        break
            
            # Method 2: Try to find specification sections in page content
            if not specs:
                specs = self._extract_specs_from_page(soup)
            
            return specs
        except Exception as e:
            print(f"Error extracting specifications: {e}")
            return specs
    
    def _parse_specifications_text(self, text):
        """Parse specification text and group into sections"""
        specs = {}
        try:
            lines = text.split('\n')
            
            current_section = None
            section_content = []
            
            # Known section names in order to capture them all
            known_sections = ['HIGHLIGHTS', 'GENERAL', 'ELECTRICAL', 'LIVING & DINNING', 
                            'BED ROOMS', 'KITCHEN', 'BALCONY', 'BATH ROOMS', 'PLUMBING', 
                            'BATHROOMS', 'STRUCTURAL', 'EXTERNAL', 'DOORS', 'WINDOWS']
            
            for line in lines:
                line_clean = line.strip()
                if not line_clean:
                    continue
                
                # Check for section headers
                is_section_header = False
                matched_section = None
                
                for known_sec in known_sections:
                    if line_clean == known_sec or (line_clean.isupper() and known_sec in line_clean):
                        is_section_header = True
                        matched_section = line_clean
                        break
                
                # Also check if it looks like an uppercase header
                if not is_section_header and line_clean.isupper() and len(line_clean) < 50:
                    is_section_header = True
                    matched_section = line_clean
                
                if is_section_header:
                    # Save previous section
                    if current_section and section_content:
                        specs[current_section] = section_content
                    
                    current_section = matched_section
                    section_content = []
                elif current_section and line_clean:
                    # Add to current section (but skip empty and very short lines)
                    if len(line_clean) > 2:
                        section_content.append(line_clean)
            
            # Don't forget the last section
            if current_section and section_content:
                specs[current_section] = section_content
            
            return specs
        except Exception as e:
            return {}
    
    def _extract_specs_from_page(self, soup):
        """Extract specifications from page content when modal not found"""
        specs = {}
        try:
            all_text = soup.get_text()
            lines = all_text.split('\n')
            
            in_specs = False
            current_section = None
            section_content = []
            
            for i, line in enumerate(lines):
                line_clean = line.strip()
                
                if 'Specification' in line_clean and not in_specs:
                    in_specs = True
                    continue
                
                if in_specs:
                    # Stop at major sections
                    if any(x in line_clean.lower() for x in ['document', 'query', 'contact', 'about us']):
                        break
                    
                    # Check if it's a section header
                    is_section_header = (line_clean.isupper() and len(line_clean) < 50 and 
                                       len(line_clean.split()) > 0)
                    
                    if is_section_header:
                        if current_section and section_content:
                            specs[current_section] = section_content
                        current_section = line_clean
                        section_content = []
                    elif current_section and line_clean and len(line_clean) < 150:
                        section_content.append(line_clean)
            
            if current_section and section_content:
                specs[current_section] = section_content
            
            return specs
        except Exception as e:
            return {}

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
    print("Starting Land Trades Scraper (Fixed)...\n")
    
    scraper.scrape_all_projects()
    
    output_path = "landtrades_projects_extracted.json"
    scraper.save_to_json(output_path)
    
    print(f"Total items scraped: {len(scraper.projects_data)}")

if __name__ == "__main__":
    main()
