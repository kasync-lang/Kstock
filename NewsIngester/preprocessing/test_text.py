from langchain_text_splitters import HTMLHeaderTextSplitter, RecursiveCharacterTextSplitter
import trafilatura
import requests
url = "https://finnhub.io/api/news?id=e7a1890bcce356d5320b1ccd6825adf9384de8965e9d8ec84944e4e42c663636"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"})


html = trafilatura.fetch_url(url)

print("\nTRAFILATURA")

if html:
    clean_html = trafilatura.extract(html, include_tables=False, output_format='html')
from langchain_text_splitters import HTMLHeaderTextSplitter

header_splitter = HTMLHeaderTextSplitter(
    headers_to_split_on=[
        ("h1", "h1"),
        ("h2", "h2"),
        ("h3", "h3"),
    ]
)

sections = header_splitter.split_text(clean_html)

# remove heading-only docs
clean_sections = []

for doc in sections:
    header_values = [
        str(v).strip()
        for k, v in doc.metadata.items()
        if k.startswith("h")
    ]

    content = doc.page_content.strip()

    if content in header_values:
        continue

    clean_sections.append(doc)


chunk_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",
    chunk_size=450,
    chunk_overlap=0,
)

chunks = chunk_splitter.split_documents(clean_sections)