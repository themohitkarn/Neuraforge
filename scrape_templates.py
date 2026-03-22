import os
import json
from bs4 import BeautifulSoup

def html_to_json(element):
    """
    Recursively converts a BeautifulSoup HTML element into a JSON-serializable dictionary structure.
    """
    if not hasattr(element, 'name') or element.name is None:
        text = str(element).strip()
        return {"type": "text", "content": text} if text else None
    
    node = {
        "tag": element.name,
        "attributes": element.attrs,
        "children": []
    }
    
    for child in element.children:
        child_node = html_to_json(child)
        if child_node:
            node["children"].append(child_node)
            
    if not node["children"]:
        del node["children"]
        
    return node

def get_asset_content(html_filepath, asset_filepath_relative):
    """
    Reads local CSS/JS files referenced in the HTML relative to the HTML file's location.
    Skipping external resources starting with http/https.
    """
    if asset_filepath_relative.startswith(('http://', 'https://', '//')):
        return "[External resource skipped]"
    
    html_dir = os.path.dirname(html_filepath)
    # clean up query params like style.css?v=1
    clean_relative_path = asset_filepath_relative.split('?')[0]
    
    # Resolve relative path
    asset_path = os.path.normpath(os.path.join(html_dir, clean_relative_path))
    
    if os.path.exists(asset_path):
        try:
            with open(asset_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"[Error reading {clean_relative_path}: {str(e)}]"
    return f"[File not found locally: {clean_relative_path}]"

def detect_framework(soup, html_text):
    """
    Attempts to identify which CSS/JS framework a given HTML template uses.
    """
    frameworks = []
    
    # Check for Tailwind
    if "tailwind" in html_text.lower():
        frameworks.append("tailwind")
    # Check common Tailwind Utility Classes since they often don't include the word 'tailwind'
    elif any(cls in html_text for cls in ["w-full", "flex-col", "items-center", "justify-between", "bg-gray-"]):
        frameworks.append("tailwind")
        
    # Check for Bootstrap
    if "bootstrap" in html_text.lower():
        frameworks.append("bootstrap")
    elif any(cls in html_text for cls in ["container-fluid", "col-md-", "col-lg-", "navbar-nav"]):
        frameworks.append("bootstrap")
        
    # Check for React (usually bundled, but we can check for common build artifacts)
    if "react" in html_text.lower() or 'id="root"' in html_text or 'data-reactroot' in html_text:
        frameworks.append("react")
        
    if not frameworks:
        return "vanilla"
        
    # Return the most prevalent framework found
    return frameworks[0]

def process_html_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        html_text = f.read()
        
    soup = BeautifulSoup(html_text, 'html.parser')
    
    # 1. Get HTML Structure (Body)
    body = soup.find('body')
    html_data = html_to_json(body) if body else html_to_json(soup)
    
    # 2. Extract CSS Content
    css_content = {}
    for link in soup.find_all('link', rel='stylesheet'):
        href = link.get('href')
        if href:
            css_content[href] = get_asset_content(filepath, href)
            
    for idx, style in enumerate(soup.find_all('style')):
        css_content[f"inline_style_{idx}"] = style.string if style.string else ""
            
    # 3. Extract JS Content
    js_content = {}
    for script in soup.find_all('script'):
        src = script.get('src')
        if src:
            js_content[src] = get_asset_content(filepath, src)
        elif script.string:
            js_content[f"inline_script"] = js_content.get(f"inline_script", "") + "\n" + script.string
            
    # 4. Auto-detect framework
    framework = detect_framework(soup, html_text)
            
    # 5. Structure data with "framework" tag
    return {
        "framework": framework,
        "html_structure": html_data,
        "css_styles": css_content,
        "javascript_logic": js_content,
        "metadata": {
            "title": soup.title.string.strip() if soup.title and soup.title.string else None
        }
    }

def scrape_directories(directories, output_json_file):
    dataset = []
    
    for directory_path in directories:
        print(f"Scanning directory: {directory_path}")
        for root, _, files in os.walk(directory_path):
            for file in files:
                if file.endswith('.html'):
                    filepath = os.path.join(root, file)
                    print(f"Processing: {filepath}")
                    try:
                        data = process_html_file(filepath)
                        dataset.append({
                            "source_file": filepath,
                            "content": data
                        })
                    except Exception as e:
                        print(f"Error processing {filepath}: {e}")
    
    with open(output_json_file, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=4)
    
    print(f"\nSuccess! Dataset saved to {output_json_file} with {len(dataset)} templates.")

if __name__ == "__main__":
    target_dirs = [
        r"d:\html-website-templates",
        r"d:\project-website-template",
        r"d:\Landing-Page",
        r"d:\Landing-page-html-bootstrap-template",
        r"d:\Modern-Portfolio-Website-Template",
        r"d:\PixelKit-Bootstrap-UI-Kits",
        r"d:\SantaGo",
        r"d:\agencia",
        r"d:\awesome-landing-pages",
        r"d:\bootstrap-bootcamp-website",
        r"d:\bootstrap5-website",
        r"d:\codrops-dropcast",
        r"d:\company-website-reactjs",
        r"d:\convert-o-matic",
        r"d:\freebies",
        r"d:\freefolio",
        r"d:\gamewebsite",
        r"d:\grav-theme-landio",
        r"d:\helgo-agency-landing",
        r"d:\nike_landing_page",
        r"d:\oldskool-html-bootstrap",
        r"d:\portfolio_one-page-template",
        r"d:\resumetemplate",
        r"d:\saas-landing-page",
        r"d:\shadcn-landing-page",
        r"d:\simple-portfolio-template",
        r"d:\tailwind-landing-page",
        r"d:\tailwind-landing-page-template",
        r"d:\unicorn-agency",
        r"d:\varadbhogayata.github.io"
    ]
    output_file = r"d:\NEURAFORGE\html_dataset.json"
    scrape_directories(target_dirs, output_file)
