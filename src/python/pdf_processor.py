#!/usr/bin/env python3
"""
PDF文獻自動化處理工具
自動將PDF文獻轉換為規範命名的文件，並生成對應的Markdown筆記
"""

import os
import re
import json
import requests
import argparse
import time
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
import openai
from pypdf import PdfReader

import logging
import sys
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(message)s',
    stream=sys.stdout
)

import dotenv

# Load environment variables
dotenv.load_dotenv()

@dataclass
class PaperInfo:
    title: str
    authors: List[str]
    year: str
    bibtex: str
    keywords: List[str] = None
    abstract: str = ""

class PDFProcessor:
    def __init__(self, openai_api_key: str = None):
        self.openai_client = openai.Client(api_key=openai_api_key) if openai_api_key else None
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """從PDF文件中提取文本"""
        try:
            reader = PdfReader(pdf_path)
            text = ""
            # 只讀取前3頁來減少token使用量
            for page_num in range(min(3, len(reader.pages))):
                text += reader.pages[page_num].extract_text()
            return text
        except Exception as e:
            logging.error(f"Failed to extract text from {pdf_path}: {e}")
            return ""
    
    def extract_doi(self, text: str) -> Optional[str]:
        """從文本中提取DOI"""
        doi_pattern = r'10\.\d{4,}(?:\.\d+)*/[-._;()\/:a-zA-Z0-9]+(?![a-zA-Z])'
        match = re.search(doi_pattern, text)
        if match:
            doi = match.group(0)
            doi = re.sub(r'[^\w/-]+$', '', doi)  # 清理DOI結尾的標點符號
            return doi
        return None
    
    def get_article_title(self, file_path: str) -> str:
        """使用OpenAI提取論文標題"""
        if not self.openai_client:
            logging.error("No OpenAI API key provided")
            return "Failed to extract title (no API key)"
        
        try:
            reader = PdfReader(file_path)
            page = reader.pages[0]
            text = page.extract_text()[:500]
            if not text:
                logging.error(f"Failed to extract text from PDF: {file_path}")
                return "Failed to extract text from the PDF."

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that extracts text from PDF files, only return pure text of the title.",
                    },
                    {
                        "role": "user",
                        "content": f"Please extract the title of the article from this {text}",
                    }
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"OpenAI API extraction failed: {e}")
            return "Failed to extract title"

class BibtexSearcher:
    def __init__(self):
        self.crossref_api = "https://api.crossref.org/works"
    
    def search_doi_by_title(self, title: str, author: str = "") -> Optional[str]:
        """根據標題搜尋DOI"""
        try:
            params = {
                'query.title': title,
                'rows': 1
            }
            if author:
                params['query.author'] = author
            
            headers = {
                'User-Agent': 'PDFProcessor/1.0 (mailto:your-email@domain.com)',
                'Accept': 'application/json'
            }
            
            response = requests.get(
                self.crossref_api, 
                params=params, 
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 429:
                logging.error("Rate limit triggered, waiting before retry")
                time.sleep(5)
                return None
            
            data = response.json()
            
            if data['message']['items']:
                return data['message']['items'][0].get('DOI')
                
        except requests.exceptions.Timeout:
            logging.error("Crossref API timeout")
        except Exception as e:
            logging.error(f"DOI search failed: {e}")
        
        return None
    
    def get_bibtex_from_doi(self, doi: str) -> str:
        """使用DOI獲取BibTeX"""
        if not doi:
            return "failed"
        
        url = f"http://dx.doi.org/{doi}"
        headers = {"Accept": "application/x-bibtex"}
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if "<title>Error: DOI Not Found</title>" in response.text:
                logging.error(f"DOI {doi} not found")
                return "failed"
            else:
                return response.text
        except Exception as e:
            logging.error(f"Failed to retrieve BibTeX for DOI {doi}: {e}")
            return "failed"
    
    def parse_bibtex_info(self, bibtex: str) -> dict:
        """從BibTeX字符串解析資訊"""
        info = {}
        
        title_match = re.search(r'title\s*=\s*\{([^}]+)\}', bibtex, re.IGNORECASE)
        info['title'] = title_match.group(1) if title_match else ''

        author_match = re.search(r'author\s*=\s*\{([^}]+)\}', bibtex, re.IGNORECASE)
        if author_match:
            authors_str = author_match.group(1)
            authors = [a.strip() for a in re.split(r'\s+and\s+', authors_str)]
            info['authors'] = authors
        else:
            info['authors'] = []
        
        year_match = re.search(r'year\s*=\s*\{?(\d{4})\}?', bibtex, re.IGNORECASE)
        info['year'] = year_match.group(1) if year_match else ''
        
        return info

    def generate_bibtex_key(self, title: str, authors: list, year: str) -> str:
        """生成kirilyuk2006complex格式的BibTeX key"""
        first_author = 'unknown'
        if authors:
            first_author_name = authors[0].split(',')[0].strip() if ',' in authors[0] else authors[0].split()[-1]
            first_author = re.sub(r'[^a-zA-Z]', '', first_author_name).lower()
        
        title_words = re.findall(r'\w+', title.lower())
        meaningful_words = [w for w in title_words if w not in ['a', 'an', 'the', 'of', 'in', 'on', 'for', 'with', 'to']]
        title_word = meaningful_words[0] if meaningful_words else 'unknown'
        
        year = re.sub(r'[^0-9]', '', str(year))
        
        return f"{first_author}{year}{title_word}"

    def customize_bibtex_key(self, bibtex: str) -> tuple:
        """替換BibTeX中的key為自定義格式"""
        if not bibtex:
            return bibtex, "No key found", "No title"
        
        parsed_info = self.parse_bibtex_info(bibtex)
        title = parsed_info['title']
        authors = parsed_info['authors']
        year = parsed_info['year']
        
        original_key_match = re.search(r'@\w+\{([^,]+),', bibtex)
        if not original_key_match:
            return bibtex, "No key found", title
        
        new_key = self.generate_bibtex_key(title, authors, year)
        new_bibtex = bibtex.replace(original_key_match.group(1), new_key)
        
        return new_bibtex, new_key, title

    def format_bibtex(self, bibtex: str) -> str:
        """格式化BibTeX使其排版整齊"""
        lines = bibtex.split('},')
        formatted_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('@'):
                formatted_lines.append(f"{line.split(',')[0]},")
                line = line.split(',')[1]
            
            formatted_line = self.format_content(line)
            if not line.endswith('}'):
                formatted_line = formatted_line + '},'
            formatted_lines.append(formatted_line)    

        return '\n'.join(formatted_lines)

    def format_content(self, line: str) -> str:
        """格式化BibTeX內容"""
        if '=' not in line:
            return f"  {line}"
        parts = line.split('=', 1)
        field = parts[0].strip()
        value = parts[1].strip().rstrip(',')
        return f"  {field:<12} = {value}"

class MarkdownGenerator:
    def __init__(self, template_path: str = None):
        self.template_path = template_path
    
    def form_template(self, bibtex: str = "", title: str = "") -> str:
        """生成Markdown模板"""
        current_date = datetime.now()
        # 如果有模板文件，讀取並替換變數
        if self.template_path and os.path.exists(self.template_path):
            try:
                with open(self.template_path, 'r', encoding='utf-8') as f:
                    template = f.read()
                
                # 替換變數
                template = template.replace('{{title}}', title)
                template = template.replace('{{bibtex}}', bibtex)
                template = template.replace('{{date}}', f"{current_date.year}/{current_date.month}/{current_date.day}")
                
                return template
            except Exception as e:
                logging.error(f"Failed to read template file {self.template_path}: {e}")
        
        # 使用預設模板
        return self._default_template(bibtex, title, current_date)
        
    def _default_template(self, bibtex: str, title: str, current_date: datetime) -> str:
        current_year = current_date.year
        current_month = current_date.month
        current_day = current_date.day

        template = f"""---
start date: {current_year}/{current_month}/{current_day}
end date: //
tags:
  -
---
# {title}

```bibtex
{bibtex}
```

## 研究背景、動機與目的

### 研究背景

### 研究動機

### 研究目的

## 文獻回顧

## 研究問題

## 研究方法

### 材料

### 實驗設計

### 量測

## 研究結果

## 討論
"""
        return template

class LiteratureProcessor:
    def __init__(self, openai_api_key: str = None, template_path: str = None):
        """初始化文獻處理器"""
        self.pdf_processor = PDFProcessor(openai_api_key)
        self.bibtex_searcher = BibtexSearcher()
        self.markdown_generator = MarkdownGenerator(template_path)
    
    def process_pdf(self, pdf_path: str, output_dir: str = ".", bibtex_path: str = "reference.bib") -> bool:
        """處理單個PDF文件"""
        try:
            # 1. 提取文字
            content = self.pdf_processor.extract_text_from_pdf(pdf_path)
            if not content:
                logging.error(f"No text extracted from {pdf_path}")
                return False
            
            # 2. 嘗試提取DOI
            doi = self.pdf_processor.extract_doi(content)
            
            if doi is None:
                title = self.pdf_processor.get_article_title(pdf_path)
                if "Failed" in title:
                    logging.error(f"Failed to extract title from {pdf_path}")
                    return False
                doi = self.bibtex_searcher.search_doi_by_title(title)
                if not doi:
                    logging.error(f"No DOI found for title: {title}")
                    return False
            
            # 3. 獲取BibTeX
            bibtex = self.bibtex_searcher.get_bibtex_from_doi(doi)
            
            if bibtex == "failed":
                logging.error(f"Failed to retrieve BibTeX for {pdf_path}")
                return False
            
            # 4. 自定義BibTeX key並格式化
            bibtex, new_key, title = self.bibtex_searcher.customize_bibtex_key(bibtex)
            formatted_bibtex = self.bibtex_searcher.format_bibtex(bibtex)
            
            # 5. 寫入reference.bib
            try:
                os.makedirs(output_dir, exist_ok=True)
                bib_path = os.path.join(output_dir, bibtex_path)
                with open(bib_path, "a", encoding='utf-8') as f:
                    f.write(formatted_bibtex + '\n')
            except Exception as e:
                logging.error(f"Failed to write BibTeX file: {e}")
                return False
            
            # 6. 生成Markdown文件
            try:
                template = self.markdown_generator.form_template(formatted_bibtex, title)
                with open(os.path.join(output_dir, f"{new_key}.md"), "w", encoding='utf-8') as f:
                    f.write(template)
            except Exception as e:
                logging.error(f"Failed to write Markdown file: {e}")
                return False
            
            # 7. 重命名PDF文件（在原位置）
            try:
                original_dir = os.path.dirname(pdf_path)
                pdf_name = f"{new_key}.pdf"
                pdf_output_path = os.path.join(original_dir, pdf_name)

                if not os.path.exists(pdf_output_path):
                    os.rename(pdf_path, pdf_output_path)
            except Exception as e:
                logging.error(f"Failed to rename PDF file: {e}")
                # 不返回False，因為主要處理已完成
            
            # 成功訊息
            logging.info(f"Successfully processed: {new_key}.md")
            return True
            
        except Exception as e:
            logging.error(f"Unexpected error processing {pdf_path}: {e}")
            return False

def main():
    """主函數，遍歷當前目錄下的所有PDF文件並處理"""
    parser = argparse.ArgumentParser(description='PDF文獻自動化處理工具')
    parser.add_argument('path', nargs='?', default='.', help='PDF文件或目錄路徑')
    parser.add_argument('-o', '--output', default='.', help='輸出目錄')
    parser.add_argument('-k', '--openai-key', help='OpenAI API Key')
    parser.add_argument('-t', '--template', help='Template file path')
    parser.add_argument('-b', '--bibtex', default='reference.bib', help='BibTeX file path')
    
    args = parser.parse_args()
    
    # 展開用戶路徑
    args.output = os.path.expanduser(args.output)
    if args.template:
        args.template = os.path.expanduser(args.template)
    
    # 從環境變量或參數獲取API key
    api_key = args.openai_key or os.getenv("OPENAI_API_KEY")
    processor = LiteratureProcessor(api_key, template_path=args.template)
    
    failed_list_path = os.path.join(args.output, "failed_list.md")
    failed_files = []
    total = 0
    failed = 0
    
    # 處理單個文件或目錄
    if os.path.isfile(args.path) and args.path.endswith('.pdf'):
        success = processor.process_pdf(args.path, args.output, args.bibtex)
        total = 1
        if not success:
            failed = 1
            failed_files.append(os.path.basename(args.path))
    elif os.path.isdir(args.path):
        for root, dirs, files in os.walk(args.path):
            for file in files:
                if file.endswith(".pdf"):
                    pdf_path = os.path.join(root, file)
                    success = processor.process_pdf(pdf_path, args.output, args.bibtex)
                    total += 1
                    if not success:
                        failed += 1
                        failed_files.append(file)
    else:
        logging.error(f"File or directory not found: {args.path}")
        return
    
    # 寫入失敗列表
    if failed_files:
        try:
            with open(failed_list_path, "w", encoding='utf-8') as f:
                f.write("Failed files:\n")
                for file in failed_files:
                    f.write(f"- {file}\n")
        except Exception as e:
            logging.error(f"Failed to write failed list: {e}")

    # 結果總結
    if total > 0:
        success_rate = ((total - failed) / total) * 100
        if failed > 0:
            logging.error(f"Processing completed: {total-failed}/{total} successful ({success_rate:.1f}%)")
        else:
            logging.info(f"All {total} files processed successfully")

if __name__ == "__main__":
    main()