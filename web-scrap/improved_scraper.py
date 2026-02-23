import requests
from bs4 import BeautifulSoup
import os
import re
import time
from urllib.parse import urljoin, urlparse
import json
from collections import defaultdict

class EnhancedRwandaScraper:
    def __init__(self):
        self.base_url = "https://www.rwandapapers.co.rw"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': self.base_url,
        })
        self.visited = set()
        self.pdf_data = []
        self.downloaded = 0
        self.pages_crawled = 0
        self.failed_downloads = []
        
        # Enhanced category structure
        self.categories = {
            'P6': 'P6_Primary_School',
            'S3': 'S3_Ordinary_Level',
            'S6': 'S6_Advanced_Level',
            'TTC': 'TTC_Teacher_Training',
            'CURRICULUM': 'Curriculum_Syllabus',
            'UNKNOWN': 'Uncategorized'
        }
        
        # Comprehensive subject mapping
        self.subject_map = {
            # P6 Subjects
            'mathematics': 'Mathematics', 'math': 'Mathematics', 'maths': 'Mathematics',
            'english': 'English', 'kinyarwanda': 'Kinyarwanda', 'kiswahili': 'Kiswahili',
            'french': 'French', 'social': 'Social_Studies', 'science': 'Science',
            
            # S3 Subjects
            'biology': 'Biology', 'chemistry': 'Chemistry', 'physics': 'Physics',
            'geography': 'Geography', 'history': 'History', 
            'entrepreneurship': 'Entrepreneurship', 'ict': 'ICT', 'computer': 'ICT',
            
            # S6 Subjects
            'economics': 'Economics', 'literature': 'Literature', 
            'religious': 'Religious_Studies', 'accounting': 'Accounting',
            'general': 'General_Paper', 'geography': 'Geography', 'history': 'History',
            
            # TTC Subjects
            'education': 'Education', 'pedagogy': 'Pedagogy', 'psychology': 'Psychology',
            'methodology': 'Methodology', 'curriculum': 'Curriculum_Studies',
            'assessment': 'Assessment', 'evaluation': 'Evaluation',
            'teaching': 'Teaching_Methods', 'learning': 'Learning_Theories',
            'classroom': 'Classroom_Management', 'foundation': 'Foundation_Studies',
            'professional': 'Professional_Studies', 'practice': 'Teaching_Practice',
        }
        
        # Priority keywords for better detection
        self.priority_keywords = {
            'P6': ['p6', 'primary 6', 'primary six', 'grade 6'],
            'S3': ['s3', 'ordinary', 'o-level', 'form 3'],
            'S6': ['s6', 'advanced', 'a-level', 'form 6'],
            'TTC': ['ttc', 'teacher training', 'teacher education', 'pedagogy', 'education'],
            'CURRICULUM': ['curriculum', 'syllabus', 'scheme of work']
        }
        
    def should_skip_url(self, url):
        """Check if URL should be skipped"""
        skip_patterns = [
            r'/feed/', r'/wp-admin/', r'/wp-login/', r'/wp-json/',
            r'\.xml$', r'\.jpg$', r'\.png$', r'\.gif$', r'\.css$', r'\.js$',
            r'/tag/', r'/author/', r'/search/', r'/cart/', r'/checkout/',
            r'/privacy', r'/terms', r'/contact', r'/about', r'/shop/',
            r'/my-account/', r'/checkout/', r'/cart/', r'\.zip$', r'\.rar$',
            r'\.mp4$', r'\.mp3$', r'\.avi$', r'\.mov$', r'/wp-content/',
            r'\.doc$', r'\.docx$', r'\.xls$', r'\.xlsx$', r'\.ppt$', r'\.pptx$'
        ]
        
        url_lower = url.lower()
        for pattern in skip_patterns:
            if re.search(pattern, url_lower, re.IGNORECASE):
                return True
        
        # Skip URLs without rwandapapers domain
        if 'rwandapapers.co.rw' not in url:
            return True
            
        return False
    
    def detect_category(self, url, page_content="", link_text=""):
        """Advanced category detection with priority system"""
        combined_text = f"{url.lower()} {page_content.lower()} {link_text.lower()}"
        
        # Check for each category with priority keywords
        for category, keywords in self.priority_keywords.items():
            for keyword in keywords:
                # Use word boundaries to avoid false positives
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, combined_text, re.IGNORECASE):
                    return category
        
        # Check URL patterns
        url_lower = url.lower()
        if 'ttc' in url_lower:
            return 'TTC'
        elif 'p6' in url_lower:
            return 'P6'
        elif 's3' in url_lower:
            return 'S3'
        elif 's6' in url_lower:
            return 'S6'
        elif 'curriculum' in url_lower or 'syllabus' in url_lower:
            return 'CURRICULUM'
        
        return 'UNKNOWN'
    
    def detect_subject(self, url, filename="", link_text=""):
        """Enhanced subject detection with context awareness"""
        combined_text = f"{url.lower()} {filename.lower()} {link_text.lower()}"
        
        # First check for exact matches with word boundaries
        for keyword, subject_name in self.subject_map.items():
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, combined_text, re.IGNORECASE):
                return subject_name
        
        # Check URL path for subject clues
        url_path = url.lower().split('/')
        for part in url_path:
            if len(part) > 3:  # Avoid short meaningless parts
                for keyword, subject_name in self.subject_map.items():
                    if keyword in part:
                        return subject_name
        
        # For TTC pages without clear subject, try to infer
        if 'ttc' in combined_text:
            if 'math' in combined_text or 'calcul' in combined_text:
                return 'Mathematics'
            elif 'english' in combined_text:
                return 'English'
            elif 'science' in combined_text:
                return 'Science'
            elif 'social' in combined_text:
                return 'Social_Studies'
            else:
                return 'Education'  # Default for TTC
        
        return 'General'
    
    def detect_year(self, url, filename="", link_text=""):
        """Advanced year detection"""
        combined_text = f"{url} {filename} {link_text}"
        
        patterns = [
            r'(20[0-2][0-9])',  # 2000-2029
            r'(19[7-9][0-9])',  # 1970-1999
            r'\b(\d{4})\b',     # Any 4-digit number
            r'(\d{2})[-_](\d{2})',  # 15-16
            r'\((\d{4})\)',     # (2015)
            r'\[(\d{4})\]',     # [2015]
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, combined_text)
            if matches:
                if isinstance(matches[0], tuple):
                    # Handle ranges like 15-16
                    try:
                        y1 = int(matches[0][0])
                        y2 = int(matches[0][1])
                        if 0 <= y1 <= 99 and 0 <= y2 <= 99:
                            return f"20{y1:02d}-20{y2:02d}"
                    except:
                        continue
                else:
                    year = str(matches[0])
                    if len(year) == 4:
                        if 1970 <= int(year) <= 2030:
                            return year
                    elif len(year) == 2:
                        y = int(year)
                        if 0 <= y <= 99:
                            return f"20{y:02d}"
        
        return "Unknown_Year"
    
    def get_all_links(self, url):
        """Get ALL links from a page - comprehensive discovery"""
        try:
            response = self.session.get(url, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            links = []
            for link in soup.find_all('a', href=True):
                href = link['href'].strip()
                link_text = link.get_text().strip()
                
                if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                    full_url = urljoin(url, href)
                    if 'rwandapapers.co.rw' in full_url:
                        links.append({
                            'url': full_url,
                            'text': link_text,
                            'title': link.get('title', '')
                        })
            
            return links
        except Exception as e:
            return []
    
    def extract_google_drive_id(self, url):
        """Extract Google Drive file ID from various URL formats"""
        patterns = [
            r'drive\.google\.com/file/d/([a-zA-Z0-9_-]{25,})',
            r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]{25,})',
            r'/uc\?.*?id=([a-zA-Z0-9_-]{25,})',
            r'id=([a-zA-Z0-9_-]{25,})',
            r'/d/([a-zA-Z0-9_-]{25,})/',
            r'/file/d/([a-zA-Z0-9_-]{25,})/view',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def find_pdf_sources(self, url):
        """Comprehensive PDF source finding - ALL methods"""
        try:
            response = self.session.get(url, timeout=15)
            content = response.text
            soup = BeautifulSoup(response.content, 'html.parser')
            
            pdf_sources = []
            found_urls = set()
            
            # Method 1: Direct Google Drive links
            for link in soup.find_all('a', href=True):
                href = link['href']
                link_text = link.get_text().strip()
                
                if 'drive.google.com' in href:
                    file_id = self.extract_google_drive_id(href)
                    if file_id and href not in found_urls:
                        found_urls.add(href)
                        pdf_sources.append({
                            'url': href,
                            'text': link_text,
                            'type': 'google_drive',
                            'file_id': file_id
                        })
            
            # Method 2: Direct PDF links
            for link in soup.find_all('a', href=True):
                href = link['href']
                link_text = link.get_text().strip()
                
                if href.lower().endswith('.pdf'):
                    absolute_url = urljoin(url, href)
                    if absolute_url not in found_urls:
                        found_urls.add(absolute_url)
                        pdf_sources.append({
                            'url': absolute_url,
                            'text': link_text,
                            'type': 'direct'
                        })
            
            # Method 3: Iframe sources
            for iframe in soup.find_all('iframe', src=True):
                src = iframe['src']
                if src and ('.pdf' in src.lower() or 'drive.google.com' in src):
                    absolute_url = urljoin(url, src)
                    if absolute_url not in found_urls:
                        found_urls.add(absolute_url)
                        pdf_sources.append({
                            'url': absolute_url,
                            'text': '',
                            'type': 'iframe'
                        })
            
            # Method 4: JavaScript embedded PDFs
            js_patterns = [
                r'["\'](https?://[^"\']+\.pdf)["\']',
                r'pdfUrl:\s*["\']([^"\']+)["\']',
                r'download.*?["\']([^"\']+\.pdf)["\']',
                r'src:\s*["\']([^"\']+\.pdf)["\']',
            ]
            
            for pattern in js_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    absolute_url = urljoin(url, match)
                    if absolute_url not in found_urls:
                        found_urls.add(absolute_url)
                        pdf_sources.append({
                            'url': absolute_url,
                            'text': '',
                            'type': 'javascript'
                        })
            
            # Method 5: Data attributes
            for element in soup.find_all(attrs={'data-file': True}):
                file_url = element['data-file']
                absolute_url = urljoin(url, file_url)
                if absolute_url not in found_urls:
                    found_urls.add(absolute_url)
                    pdf_sources.append({
                        'url': absolute_url,
                        'text': element.get_text().strip(),
                        'type': 'data_attribute'
                    })
            
            # Method 6: Embed tags
            for embed in soup.find_all('embed', src=True):
                src = embed['src']
                if '.pdf' in src.lower():
                    absolute_url = urljoin(url, src)
                    if absolute_url not in found_urls:
                        found_urls.add(absolute_url)
                        pdf_sources.append({
                            'url': absolute_url,
                            'text': '',
                            'type': 'embed'
                        })
            
            # Method 7: Object tags
            for obj in soup.find_all('object', data=True):
                data = obj['data']
                if '.pdf' in data.lower():
                    absolute_url = urljoin(url, data)
                    if absolute_url not in found_urls:
                        found_urls.add(absolute_url)
                        pdf_sources.append({
                            'url': absolute_url,
                            'text': '',
                            'type': 'object'
                        })
            
            return pdf_sources
            
        except Exception as e:
            return []
    
    def generate_filename(self, pdf_info, category, subject, year, source_url):
        """Generate descriptive filename"""
        parts = []
        
        # Always include category
        if category != 'UNKNOWN':
            parts.append(self.categories[category].replace(' ', '_'))
        
        # Always include subject
        parts.append(subject.replace(' ', '_'))
        
        # Include year if available (not "Unknown_Year")
        if year and year != "Unknown_Year":
            parts.append(str(year).replace(' ', '_'))
        
        # Add meaningful text from link
        if pdf_info.get('text'):
            clean_text = re.sub(r'[^\w\s-]', '', pdf_info['text'])
            clean_text = re.sub(r'\s+', '_', clean_text).strip()
            if clean_text and len(clean_text) > 3:
                # Remove parts already in filename
                text_lower = clean_text.lower()
                skip_words = [cat.lower() for cat in parts] + \
                            [kw for kw in ['download', 'pdf', 'file', 'link']]
                
                if not any(word in text_lower for word in skip_words):
                    parts.append(clean_text[:40])
        
        # Add source URL component if needed
        if len(parts) < 3:
            url_parts = urlparse(source_url).path.split('/')
            for part in reversed(url_parts):
                if part and len(part) > 3:
                    clean_part = re.sub(r'[^\w-]', '_', part)
                    if clean_part not in ' '.join(parts).lower():
                        parts.append(clean_part[:30])
                        break
        
        # Ensure unique filename
        filename = '_'.join(parts) + '.pdf'
        filename = re.sub(r'[^\w\-\.]', '_', filename)
        filename = re.sub(r'_+', '_', filename)
        
        # Add timestamp if too generic
        if len(filename) < 15:
            timestamp = str(int(time.time()))[-6:]
            filename = filename.replace('.pdf', f'_{timestamp}.pdf')
        
        return filename
    
    def download_google_drive_file(self, file_id, filepath):
        """Download from Google Drive with error handling"""
        try:
            # Try multiple download methods
            methods = [
                f"https://drive.google.com/uc?export=download&id={file_id}",
                f"https://drive.google.com/u/0/uc?id={file_id}&export=download",
            ]
            
            for url in methods:
                try:
                    response = self.session.get(url, stream=True, timeout=30)
                    
                    # Handle virus scan warning
                    if 'content-disposition' not in response.headers:
                        # Check cookies for confirm token
                        for key, value in response.cookies.items():
                            if 'download_warning' in key:
                                url = f"{url}&confirm={value}"
                                response = self.session.get(url, stream=True, timeout=30)
                                break
                    
                    # Save file
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    # Verify download
                    if os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
                        # Check if it's actually a PDF
                        with open(filepath, 'rb') as f:
                            header = f.read(5)
                            if header.startswith(b'%PDF-'):
                                return True, "Google Drive download successful"
                    
                except Exception as e:
                    continue
            
            return False, "All Google Drive methods failed"
            
        except Exception as e:
            return False, f"Google Drive error: {str(e)}"
    
    def validate_pdf(self, filepath):
        """Validate downloaded PDF file"""
        try:
            if not os.path.exists(filepath):
                return False, "File doesn't exist"
            
            file_size = os.path.getsize(filepath)
            if file_size < 1024:  # Less than 1KB
                return False, f"File too small ({file_size} bytes)"
            
            # Check PDF header
            with open(filepath, 'rb') as f:
                header = f.read(10)
                if not header.startswith(b'%PDF-'):
                    # Check if it's HTML (error page)
                    f.seek(0)
                    content = f.read(1024).lower()
                    if b'<!doctype' in content or b'<html' in content:
                        return False, "HTML file (not PDF)"
                    return False, "Not a valid PDF file"
            
            return True, f"Valid PDF ({file_size/1024:.1f} KB)"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def download_pdf(self, pdf_info, source_url, output_base="rwanda_papers"):
        """Download and organize PDF with deep folder structure"""
        try:
            pdf_url = pdf_info['url']
            
            # Detect metadata with enhanced algorithms
            category = self.detect_category(source_url, "", pdf_info.get('text', ''))
            subject = self.detect_subject(pdf_url, pdf_url, pdf_info.get('text', ''))
            year = self.detect_year(pdf_url, pdf_url, pdf_info.get('text', ''))
            
            # Generate filename
            filename = self.generate_filename(pdf_info, category, subject, year, source_url)
            
            # Create hierarchical folder structure
            folder_parts = [output_base]
            
            # Main category folder
            folder_parts.append(self.categories[category])
            
            # Subject folder (always created)
            subject_folder = subject.replace('/', '_').replace('\\', '_')
            folder_parts.append(subject_folder)
            
            # Year folder if year is detected (not "Unknown_Year")
            if year and year != "Unknown_Year":
                folder_parts.append(str(year))
            
            folder_path = os.path.join(*folder_parts)
            os.makedirs(folder_path, exist_ok=True)
            
            filepath = os.path.join(folder_path, filename)
            
            # Check for existing file
            if os.path.exists(filepath):
                is_valid, msg = self.validate_pdf(filepath)
                if is_valid:
                    print(f"    ⏭️  Skip: {filename}")
                    return True
                else:
                    print(f"    🔄 Re-download: {msg}")
                    os.remove(filepath)
            
            print(f"    📥 {filename}")
            print(f"       📁 {os.path.relpath(folder_path, output_base)}")
            print(f"       🏷️  {subject} | 📅 {year}")
            
            # Download based on type
            success = False
            if pdf_info.get('type') == 'google_drive' and pdf_info.get('file_id'):
                success, msg = self.download_google_drive_file(
                    pdf_info['file_id'], 
                    filepath
                )
                if success:
                    print(f"    ✅ {msg}")
                else:
                    print(f"    ❌ Google Drive: {msg}")
            else:
                # Direct download
                try:
                    response = self.session.get(pdf_url, stream=True, timeout=30)
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    success = True
                except Exception as e:
                    print(f"    ❌ Direct download failed: {e}")
                    success = False
            
            # Validate download
            if success:
                is_valid, msg = self.validate_pdf(filepath)
                if is_valid:
                    file_size = os.path.getsize(filepath)
                    print(f"    ✅ {file_size/1024:.1f} KB")
                    
                    self.downloaded += 1
                    self.pdf_data.append({
                        'url': pdf_url,
                        'source_page': source_url,
                        'category': category,
                        'subject': subject,
                        'year': year,
                        'filename': filename,
                        'filepath': filepath,
                        'file_size': file_size,
                        'download_time': time.strftime('%Y-%m-%d %H:%M:%S')
                    })
                    return True
                else:
                    print(f"    ❌ Invalid file: {msg}")
                    if os.path.exists(filepath):
                        os.remove(filepath)
            
            # Record failure
            self.failed_downloads.append({
                'url': pdf_url,
                'filename': filename,
                'category': category,
                'subject': subject,
                'reason': 'Download failed' if not success else 'Validation failed'
            })
            return False
            
        except Exception as e:
            print(f"    ❌ Error: {str(e)[:100]}")
            self.failed_downloads.append({
                'url': pdf_info.get('url', 'unknown'),
                'filename': filename if 'filename' in locals() else 'unknown',
                'reason': str(e)
            })
            return False
    
    def crawl_deep_recursive(self, start_urls, max_pages=1000, max_depth=10):
        """Deep recursive crawl that explores ALL nested links"""
        print(f"\n🚀 DEEP RECURSIVE CRAWL")
        print(f"   Max pages: {max_pages} | Max depth: {max_depth}")
        print("=" * 80)
        
        # Queue: (url, depth, parent_url)
        queue = [(url, 0, 'START') for url in start_urls]
        
        while queue and self.pages_crawled < max_pages:
            current_url, depth, parent = queue.pop(0)
            
            if current_url in self.visited:
                continue
            
            if self.should_skip_url(current_url):
                continue
            
            if depth > max_depth:
                continue
            
            self.visited.add(current_url)
            self.pages_crawled += 1
            
            # Display with depth indicator
            indent = "  " * depth
            url_display = current_url.replace(self.base_url, '')
            if len(url_display) > 60:
                url_display = '...' + url_display[-57:]
            
            print(f"\n{indent}[{self.pages_crawled}] Depth {depth}: {url_display}")
            
            try:
                # Find and download PDFs
                pdf_sources = self.find_pdf_sources(current_url)
                
                if pdf_sources:
                    print(f"{indent}  📄 Found {len(pdf_sources)} PDF(s)")
                    for pdf_info in pdf_sources:
                        self.download_pdf(pdf_info, current_url)
                        time.sleep(0.3)
                
                # Discover new links
                if depth < max_depth:
                    all_links = self.get_all_links(current_url)
                    new_links = 0
                    
                    for link_info in all_links:
                        link_url = link_info['url']
                        
                        if (link_url not in self.visited and 
                            link_url not in [q[0] for q in queue] and
                            not self.should_skip_url(link_url)):
                            
                            # Priority for TTC and specific categories
                            priority = 0
                            if 'ttc' in link_url.lower():
                                priority = 2
                            elif any(cat in link_url.lower() for cat in ['p6', 's3', 's6']):
                                priority = 1
                            
                            queue.insert(priority, (link_url, depth + 1, current_url))
                            new_links += 1
                    
                    if new_links > 0:
                        print(f"{indent}  🔗 +{new_links} links (Queue: {len(queue)})")
                
                # Progress report
                if self.pages_crawled % 20 == 0:
                    self.show_progress_report()
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"{indent}  ❌ Error: {str(e)[:50]}")
                continue
        
        self.show_final_report()
    
    def show_progress_report(self):
        """Show detailed progress report"""
        print(f"\n{'='*80}")
        
        # Count by category
        cat_counts = defaultdict(int)
        subj_counts = defaultdict(lambda: defaultdict(int))
        
        for pdf in self.pdf_data:
            cat = pdf['category']
            subj = pdf['subject']
            cat_counts[cat] += 1
            subj_counts[cat][subj] += 1
        
        print(f"📊 PROGRESS REPORT")
        print(f"   Pages crawled: {self.pages_crawled}")
        print(f"   PDFs downloaded: {self.downloaded}")
        print(f"   Failed downloads: {len(self.failed_downloads)}")
        print()
        
        print(f"   BY CATEGORY:")
        for cat in ['TTC', 'P6', 'S3', 'S6', 'CURRICULUM', 'UNKNOWN']:
            if cat_counts[cat] > 0:
                print(f"     {self.categories[cat]}: {cat_counts[cat]} files")
                if cat in subj_counts:
                    for subj, count in sorted(subj_counts[cat].items()):
                        print(f"       {subj}: {count}")
        
        print(f"{'='*80}")
    
    def show_final_report(self):
        """Show final comprehensive report"""
        print("\n" + "=" * 80)
        print("✅ CRAWL COMPLETE!")
        print("=" * 80)
        
        # Organize data for reporting
        by_category = defaultdict(list)
        for pdf in self.pdf_data:
            by_category[pdf['category']].append(pdf)
        
        # Summary
        print(f"\n📋 SUMMARY:")
        print(f"   Total pages crawled: {self.pages_crawled}")
        print(f"   Total PDFs downloaded: {self.downloaded}")
        print(f"   Failed downloads: {len(self.failed_downloads)}")
        print(f"   Unique URLs visited: {len(self.visited)}")
        
        # Detailed breakdown
        print(f"\n📁 FOLDER STRUCTURE CREATED:")
        for cat in ['TTC', 'P6', 'S3', 'S6', 'CURRICULUM']:
            if cat in by_category:
                cat_name = self.categories[cat]
                count = len(by_category[cat])
                
                # Get unique subjects in this category
                subjects = set(pdf['subject'] for pdf in by_category[cat])
                
                print(f"\n   {cat_name}: {count} files")
                print(f"   Subjects: {', '.join(sorted(subjects))}")
                
                # Show sample files
                if by_category[cat]:
                    print(f"   Sample files:")
                    for pdf in by_category[cat][:3]:  # First 3 files
                        rel_path = os.path.relpath(pdf['filepath'], 'rwanda_papers')
                        print(f"     • {rel_path}")
        
        print("\n" + "=" * 80)
    
    def save_results(self, output_base="rwanda_papers"):
        """Save all results with comprehensive metadata"""
        os.makedirs(output_base, exist_ok=True)
        
        # 1. Comprehensive metadata
        metadata = {
            'crawl_info': {
                'date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_pages': self.pages_crawled,
                'total_pdfs': self.downloaded,
                'failed_downloads': len(self.failed_downloads),
                'categories': self.categories
            },
            'pdfs': self.pdf_data,
            'failed': self.failed_downloads,
            'visited_urls': list(self.visited)[:1000]  # First 1000 URLs
        }
        
        with open(os.path.join(output_base, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # 2. Detailed report with safe sorting
        with open(os.path.join(output_base, 'detailed_report.txt'), 'w') as f:
            f.write("RWANDA PAPERS - DEEP CRAWL REPORT\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Crawl Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Pages Crawled: {self.pages_crawled}\n")
            f.write(f"PDFs Downloaded: {self.downloaded}\n")
            f.write(f"Failed Downloads: {len(self.failed_downloads)}\n\n")
            
            # Organize by category
            by_category = defaultdict(lambda: defaultdict(list))
            for pdf in self.pdf_data:
                by_category[pdf['category']][pdf['subject']].append(pdf)
            
            for cat in sorted(by_category.keys()):
                f.write(f"\n{'='*60}\n")
                f.write(f"{self.categories[cat].upper()}\n")
                f.write(f"{'='*60}\n")
                
                total = sum(len(pdfs) for pdfs in by_category[cat].values())
                f.write(f"Total Files: {total}\n\n")
                
                for subj in sorted(by_category[cat].keys()):
                    pdfs = by_category[cat][subj]
                    f.write(f"{subj}: {len(pdfs)} files\n")
                    
                    # Sort files by year (safely handle None/Unknown_Year)
                    def get_sort_key(pdf):
                        year = pdf.get('year', '')
                        # Put Unknown_Year at the end, sort actual years normally
                        if year == "Unknown_Year" or not year:
                            return ('zzz', pdf.get('filename', ''))
                        return (year, pdf.get('filename', ''))
                    
                    for pdf in sorted(pdfs, key=get_sort_key):
                        f.write(f"  • {pdf['filename']}")
                        if pdf.get('year') and pdf['year'] != "Unknown_Year":
                            f.write(f" [{pdf['year']}]")
                        f.write(f" ({pdf['file_size']/1024:.1f} KB)\n")
                    f.write("\n")
        
        # 3. Simple summary report
        with open(os.path.join(output_base, 'summary.txt'), 'w') as f:
            f.write("QUICK SUMMARY\n")
            f.write("=" * 60 + "\n\n")
            
            by_cat_subj = defaultdict(lambda: defaultdict(int))
            for pdf in self.pdf_data:
                by_cat_subj[pdf['category']][pdf['subject']] += 1
            
            f.write("Files by Category and Subject:\n")
            f.write("-" * 60 + "\n")
            for cat in ['TTC', 'P6', 'S3', 'S6', 'CURRICULUM', 'UNKNOWN']:
                if cat in by_cat_subj:
                    f.write(f"\n{self.categories[cat]}:\n")
                    for subj, count in sorted(by_cat_subj[cat].items()):
                        f.write(f"  {subj}: {count} files\n")
        
        print(f"\n💾 Results saved to {output_base}/")
        print(f"   • metadata.json - Complete crawl data")
        print(f"   • detailed_report.txt - Organized file listing")
        print(f"   • summary.txt - Quick overview")
        
        if self.failed_downloads:
            print(f"   ⚠️  {len(self.failed_downloads)} failed downloads (see metadata.json)")


def main():
    print("=" * 80)
    print(" 🎓 ENHANCED RWANDA PAPERS DEEP SCRAPER")
    print("=" * 80)
    print("\n✨ Features:")
    print("  • Deep recursive crawling (explores ALL links)")
    print("  • Enhanced TTC detection and organization")
    print("  • Hierarchical folder structure: Category/Subject/Year/")
    print("  • Comprehensive PDF detection (Google Drive, direct, embedded)")
    print("  • Smart filename generation with context")
    print("=" * 80)
    
    scraper = EnhancedRwandaScraper()
    
    # Comprehensive start URLs
    start_urls = [
        # Main category pages
        "https://www.rwandapapers.co.rw/p6-past-papers",
        "https://www.rwandapapers.co.rw/s3-past-papers", 
        "https://www.rwandapapers.co.rw/s6-past-papers",
        "https://www.rwandapapers.co.rw/ttc-past-papers",
        
        # Specific TTC pages
        "https://www.rwandapapers.co.rw/ttc",
        "https://www.rwandapapers.co.rw/teacher-training",
        
        # Curriculum pages
        "https://www.rwandapapers.co.rw/curriculum",
        "https://www.rwandapapers.co.rw/syllabus",
        
        # Homepage and sitemap
        "https://www.rwandapapers.co.rw",
        "https://www.rwandapapers.co.rw/sitemap",
        "https://www.rwandapapers.co.rw/sitemap.xml",
    ]
    
    print(f"\n📋 Starting with {len(start_urls)} initial URLs")
    
    # Show TTC URLs specifically
    ttc_urls = [url for url in start_urls if 'ttc' in url.lower()]
    if ttc_urls:
        print("   TTC URLs:", ttc_urls)
    
    # Configuration
    try:
        max_pages = input("\nMax pages to crawl (default 200): ").strip()
        max_pages = int(max_pages) if max_pages else 200
        
        max_depth = input("Max crawl depth (default 4): ").strip()
        max_depth = int(max_depth) if max_depth else 4
        
        print(f"\n⚙️  Configuration:")
        print(f"   Max pages: {max_pages}")
        print(f"   Max depth: {max_depth}")
        print(f"   Output folder: rwanda_papers/")
        
        if input("\nStart crawling? (y/n): ").lower() == 'y':
            scraper.crawl_deep_recursive(start_urls, max_pages, max_depth)
            scraper.save_results()
            
            print("\n" + "=" * 80)
            print("✅ CRAWL COMPLETE!")
            print("=" * 80)
            print("\n📁 Organized files in: rwanda_papers/")
            print("   Structure: Category/Subject/Year/filename.pdf")
            print("\n📊 Check detailed_report.txt for complete listing")
        else:
            print("\n❌ Crawl cancelled")
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Crawl interrupted by user")
        scraper.show_final_report()
        scraper.save_results()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        scraper.save_results()


if __name__ == "__main__":
    main()