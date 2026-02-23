import requests
from bs4 import BeautifulSoup
import os
import re
import time
from urllib.parse import urljoin, urlparse
import json
from collections import defaultdict

class DeepRwandaScraper:
    def __init__(self):
        self.base_url = "https://www.rwandapapers.co.rw"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        self.visited = set()
        self.pdf_data = []
        self.downloaded = 0
        self.pages_crawled = 0
        
        # Folder structure
        self.categories = {
            'P6': 'Primary_School_P6',
            'S3': 'Ordinary_Level_S3',
            'S6': 'Advanced_Level_S6',
            'TTC': 'TTC',
            'CURRICULUM': 'Curriculum',
            'UNKNOWN': 'Uncategorized'
        }
        
        # Subject patterns
        self.subjects = [
            'mathematics', 'math', 'maths', 'english', 'kinyarwanda', 'kiswahili',
            'french', 'biology', 'chemistry', 'physics', 'geography',
            'history', 'entrepreneurship', 'ict', 'computer', 'economics',
            'literature', 'religious', 'social', 'science', 'general'
        ]
        
    def detect_category(self, url, page_content="", link_text=""):
        """Detect which category a PDF belongs to"""
        combined_text = f"{url} {page_content} {link_text}".lower()
        
        if any(x in combined_text for x in ['p6', 'primary', 'primary-school']):
            return 'P6'
        elif any(x in combined_text for x in ['s3', 'ordinary', 'o-level', 'olevel']):
            return 'S3'
        elif any(x in combined_text for x in ['s6', 'advanced', 'a-level', 'alevel']):
            return 'S6'
        elif 'ttc' in combined_text:
            return 'TTC'
        elif any(x in combined_text for x in ['curriculum', 'syllabus']):
            return 'CURRICULUM'
        
        return 'UNKNOWN'
    
    def detect_subject(self, url, filename="", link_text=""):
        """Detect the subject"""
        combined_text = f"{url} {filename} {link_text}".lower()
        
        for subject in self.subjects:
            if subject in combined_text:
                return subject.capitalize()
        
        return 'General'
    
    def detect_year(self, url, filename="", link_text=""):
        """Extract year"""
        combined_text = f"{url} {filename} {link_text}"
        
        # Look for 4-digit years (2000-2099)
        year_match = re.search(r'20[0-9]{2}', combined_text)
        if year_match:
            return year_match.group(0)
        
        # Look for 2-digit years
        year_match = re.search(r'[^0-9]([0-9]{2})[^0-9]', combined_text)
        if year_match:
            year = int(year_match.group(1))
            if year >= 0 and year <= 50:
                return f"20{year:02d}"
        
        return None
    
    def get_all_links(self, url):
        """Get ALL links from a page - no filtering yet"""
        try:
            response = self.session.get(url, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            links = []
            for link in soup.find_all('a', href=True):
                href = link['href'].strip()
                link_text = link.get_text().strip()
                
                if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                    full_url = urljoin(url, href)
                    # Only get links from same domain
                    if 'rwandapapers.co.rw' in full_url:
                        links.append({
                            'url': full_url,
                            'text': link_text
                        })
            
            return links
        except Exception as e:
            print(f"  ⚠️  Error getting links: {e}")
            return []
    
    def find_pdf_sources(self, url):
        """Find all PDF sources on a page"""
        try:
            response = self.session.get(url, timeout=15)
            content = response.text
            soup = BeautifulSoup(response.content, 'html.parser')
            
            pdf_sources = []
            
            # 1. Google Drive patterns
            drive_patterns = [
                r'https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)/view',
                r'https://drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
                r'src="https://drive\.google\.com/[^"]+',
            ]
            
            for pattern in drive_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if isinstance(match, str) and len(match) > 20:
                        pdf_sources.append({
                            'url': f"https://drive.google.com/file/d/{match}/view",
                            'text': '',
                            'type': 'google_drive',
                            'file_id': match
                        })
            
            # 2. Direct PDF links
            pdf_links = re.findall(r'href="([^"]+\.pdf)"', content, re.IGNORECASE)
            for pdf_link in pdf_links:
                absolute_url = urljoin(url, pdf_link)
                pdf_sources.append({
                    'url': absolute_url,
                    'text': '',
                    'type': 'direct'
                })
            
            # 3. Iframe sources
            iframe_srcs = re.findall(r'<iframe[^>]+src="([^"]+)"', content, re.IGNORECASE)
            for src in iframe_srcs:
                if '.pdf' in src.lower() or 'drive.google.com' in src:
                    absolute_url = urljoin(url, src)
                    pdf_sources.append({
                        'url': absolute_url,
                        'text': '',
                        'type': 'iframe'
                    })
            
            # 4. JavaScript PDF URLs
            js_vars = re.findall(r'["\'](https?://[^"\']+\.pdf)["\']', content, re.IGNORECASE)
            for js_var in js_vars:
                pdf_sources.append({
                    'url': js_var,
                    'text': '',
                    'type': 'javascript'
                })
            
            # 5. Data attributes
            download_buttons = re.findall(r'data-(?:file|pdf|url)="([^"]+)"', content, re.IGNORECASE)
            for button_url in download_buttons:
                absolute_url = urljoin(url, button_url)
                pdf_sources.append({
                    'url': absolute_url,
                    'text': '',
                    'type': 'data_attribute'
                })
            
            # Add link text for better categorization
            for link in soup.find_all('a', href=True):
                href = link['href']
                link_text = link.get_text().strip()
                for source in pdf_sources:
                    if href in source['url']:
                        source['text'] = link_text
            
            return pdf_sources
            
        except Exception as e:
            print(f"  ⚠️  Error finding PDFs: {e}")
            return []
    
    def generate_filename(self, pdf_info, category, subject, year, source_url):
        """Generate a clean, descriptive filename"""
        parts = []
        
        # Add category
        if category != 'UNKNOWN':
            parts.append(category)
        
        # Add subject
        if subject and subject != 'General':
            parts.append(subject)
        
        # Add year
        if year:
            parts.append(year)
        
        # Add link text if available
        if pdf_info.get('text'):
            clean_text = re.sub(r'[^\w\s-]', '', pdf_info['text'])
            clean_text = re.sub(r'\s+', '_', clean_text)
            if clean_text and len(clean_text) > 3:
                parts.append(clean_text[:50])
        
        # If still no good name, extract from URL
        if len(parts) <= 2:
            url_parts = source_url.split('/')
            for part in reversed(url_parts):
                if part and part not in ['https:', 'www.rwandapapers.co.rw', '']:
                    clean_part = re.sub(r'[^\w-]', '_', part)
                    if len(clean_part) > 3:
                        parts.append(clean_part[:30])
                        break
        
        # If still nothing, use timestamp
        if not parts:
            parts.append(f"document_{int(time.time())}")
        
        filename = '_'.join(parts) + '.pdf'
        filename = re.sub(r'[^\w\-\.]', '_', filename)
        filename = re.sub(r'_+', '_', filename)
        
        return filename
    
    def download_pdf(self, pdf_info, source_url, output_base="rwanda_papers_organized"):
        """Download and organize a PDF"""
        try:
            pdf_url = pdf_info['url']
            
            # Detect metadata
            category = self.detect_category(source_url, source_url, pdf_info.get('text', ''))
            subject = self.detect_subject(pdf_url, pdf_url, pdf_info.get('text', ''))
            year = self.detect_year(pdf_url, pdf_url, pdf_info.get('text', ''))
            
            # Generate filename
            filename = self.generate_filename(pdf_info, category, subject, year, source_url)
            
            # Create folder structure
            folder_path = os.path.join(
                output_base,
                self.categories[category],
                subject if subject else 'General'
            )
            os.makedirs(folder_path, exist_ok=True)
            
            filepath = os.path.join(folder_path, filename)
            
            # Skip if exists
            if os.path.exists(filepath):
                print(f"    ⏭️  Skip: {filename}")
                return True
            
            print(f"    📥 Downloading: {filename}")
            
            # Download
            if 'drive.google.com' in pdf_url:
                file_id_match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', pdf_url)
                if file_id_match:
                    file_id = file_id_match.group(1)
                    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                    response = self.session.get(download_url, stream=True, timeout=30)
                else:
                    response = self.session.get(pdf_url, stream=True, timeout=30)
            else:
                response = self.session.get(pdf_url, stream=True, timeout=30)
            
            # Save file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Verify size
            file_size = os.path.getsize(filepath)
            if file_size < 1024:
                print(f"    ❌ Too small ({file_size} bytes), deleting")
                os.remove(filepath)
                return False
            
            print(f"    ✅ Success: {file_size / 1024:.1f} KB")
            self.downloaded += 1
            
            # Save metadata
            self.pdf_data.append({
                'url': pdf_url,
                'source_page': source_url,
                'category': category,
                'subject': subject,
                'year': year,
                'filename': filename,
                'filepath': filepath,
                'file_size': file_size
            })
            
            return True
            
        except Exception as e:
            print(f"    ❌ Failed: {e}")
            return False
    
    def should_skip_url(self, url):
        """Check if we should skip this URL entirely"""
        skip_patterns = [
            r'/feed/', r'/wp-admin/', r'/wp-login/', r'/wp-json/',
            r'\.xml$', r'\.jpg$', r'\.png$', r'\.gif$', r'\.css$', r'\.js$',
            r'/tag/', r'/author/', r'/search/', r'/cart/', r'/checkout/',
            r'/privacy', r'/terms', r'/contact', r'/about'
        ]
        
        for pattern in skip_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False
    
    def crawl_deep(self, start_urls, max_pages=1000):
        """Deep recursive crawl - go through ALL links"""
        print(f"\n🚀 DEEP CRAWL MODE - Will explore ALL nested links")
        print(f"   Max pages: {max_pages}")
        print("=" * 80)
        
        # Use a queue: (url, depth, parent_url)
        queue = [(url, 0, 'START') for url in start_urls]
        
        while queue and self.pages_crawled < max_pages:
            current_url, depth, parent = queue.pop(0)
            
            # Skip if already visited
            if current_url in self.visited:
                continue
            
            # Skip certain URLs
            if self.should_skip_url(current_url):
                continue
            
            self.visited.add(current_url)
            self.pages_crawled += 1
            
            # Show progress
            indent = "  " * depth
            print(f"\n{indent}[Page {self.pages_crawled}] Depth {depth}: {current_url}")
            
            try:
                # Find PDFs on this page
                pdf_sources = self.find_pdf_sources(current_url)
                
                if pdf_sources:
                    print(f"{indent}  📄 Found {len(pdf_sources)} PDF(s)")
                    for pdf_info in pdf_sources:
                        self.download_pdf(pdf_info, current_url)
                        time.sleep(0.5)
                
                # Get ALL links from this page
                all_links = self.get_all_links(current_url)
                new_links = 0
                
                for link_info in all_links:
                    link_url = link_info['url']
                    
                    # Only add if not visited and not in queue
                    if link_url not in self.visited and link_url not in [q[0] for q in queue]:
                        queue.append((link_url, depth + 1, current_url))
                        new_links += 1
                
                if new_links > 0:
                    print(f"{indent}  🔗 Added {new_links} new links to queue (Queue size: {len(queue)})")
                
                # Progress summary
                if self.pages_crawled % 10 == 0:
                    print(f"\n{'='*80}")
                    print(f"📊 PROGRESS: {self.pages_crawled} pages | {self.downloaded} PDFs | {len(queue)} queued")
                    print(f"{'='*80}")
                
                time.sleep(0.5)  # Be polite
                
            except Exception as e:
                print(f"{indent}  ❌ Error: {e}")
                continue
        
        print("\n" + "=" * 80)
        print(f"✅ CRAWL COMPLETE!")
        print(f"   Pages visited: {self.pages_crawled}")
        print(f"   PDFs downloaded: {self.downloaded}")
        print(f"   Remaining queue: {len(queue)}")
        print("=" * 80)
    
    def save_metadata(self, output_base="rwanda_papers_organized"):
        """Save metadata"""
        os.makedirs(output_base, exist_ok=True)
        metadata_file = os.path.join(output_base, 'download_metadata.json')
        
        metadata = {
            'crawl_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_pages_visited': self.pages_crawled,
            'total_pdfs_downloaded': self.downloaded,
            'pdfs': self.pdf_data,
            'categories': self.categories
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Metadata saved to: {metadata_file}")
    
    def generate_report(self, output_base="rwanda_papers_organized"):
        """Generate summary report"""
        os.makedirs(output_base, exist_ok=True)
        report_file = os.path.join(output_base, 'download_report.txt')
        
        by_category = defaultdict(list)
        for pdf in self.pdf_data:
            by_category[pdf['category']].append(pdf)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("RWANDA PAPERS DEEP CRAWL REPORT\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Crawl Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Pages Visited: {self.pages_crawled}\n")
            f.write(f"PDFs Downloaded: {self.downloaded}\n\n")
            
            f.write("DOWNLOADS BY CATEGORY:\n")
            f.write("-" * 80 + "\n")
            
            for category in sorted(by_category.keys()):
                pdfs = by_category[category]
                f.write(f"\n{self.categories[category]}: {len(pdfs)} files\n")
                
                by_subject = defaultdict(list)
                for pdf in pdfs:
                    by_subject[pdf['subject']].append(pdf)
                
                for subject in sorted(by_subject.keys()):
                    subject_pdfs = by_subject[subject]
                    f.write(f"  - {subject}: {len(subject_pdfs)} files\n")
        
        print(f"📊 Report saved to: {report_file}")


def main():
    print("=" * 80)
    print(" 🎓 DEEP RECURSIVE RWANDA PAPERS SCRAPER")
    print("=" * 80)
    print("\n⚡ This scraper will:")
    print("  • Crawl through ALL nested links (categories → subjects → lessons → PDFs)")
    print("  • Download every PDF it finds")
    print("  • Organize files by category and subject")
    print("  • No depth limit - explores everything!")
    print("=" * 80)
    
    scraper = DeepRwandaScraper()
    
    # Start URLs
    start_urls = [
        "https://www.rwandapapers.co.rw/p6-past-papers",
        "https://www.rwandapapers.co.rw/s3-past-papers",
        "https://www.rwandapapers.co.rw/s6-past-papers",
        "https://www.rwandapapers.co.rw/ttc-past-papers",
    ]
    
    # Try to discover more from homepage
    try:
        print("\n🔍 Discovering URLs from homepage...")
        response = scraper.session.get("https://www.rwandapapers.co.rw", timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            if any(kw in href.lower() for kw in ['past', 'paper', 'curriculum', 'p6', 's3', 's6', 'ttc']):
                full_url = urljoin(scraper.base_url, href)
                if full_url not in start_urls:
                    start_urls.append(full_url)
        
        print(f"   Total start URLs: {len(start_urls)}")
    except:
        pass
    
    # Configure
    max_pages = input("\nMax pages to crawl (default 1000, enter 0 for unlimited): ").strip()
    max_pages = int(max_pages) if max_pages else 1000
    if max_pages == 0:
        max_pages = 999999
    
    confirm = input(f"\nStart deep crawl? This will explore ALL nested links. (y/n): ").strip().lower()
    
    if confirm == 'y':
        # Start crawling
        scraper.crawl_deep(start_urls, max_pages=max_pages)
        
        # Save results
        scraper.save_metadata()
        scraper.generate_report()
        
        print("\n" + "=" * 80)
        print("✅ COMPLETE!")
        print("=" * 80)
        print("\n📁 Files: rwanda_papers_organized/")
        print("📊 Report: rwanda_papers_organized/download_report.txt")
        print("💾 Metadata: rwanda_papers_organized/download_metadata.json")
    else:
        print("\n❌ Cancelled")


if __name__ == "__main__":
    main()
