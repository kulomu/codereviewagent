from pathlib import Path
from lxml import etree
from llama_index.core.schema import TextNode
import requests
import json
import tempfile

# XML 檔案所在資料夾
XML_DIR = Path("docs")

# Dify 設定
DIFY_BASE_URL = "https://dify.staging.link/v1"
DATASET_ID = "7880634d-cef2-4825-965a-2b3450261429"
DIFY_API_KEY = "dataset-SAKwbC3Isvw1qPew3EsWGBFh"

# 將單一 XML 解析成 TextNode chunks
def parse_xml_file_to_nodes(file_path: Path) -> list[TextNode]:
    try:
        parser = etree.XMLParser(recover=True)  # 加上 recover 模式，容錯特殊字符問題
        tree = etree.parse(str(file_path), parser=parser)
        root = tree.getroot()
    except etree.XMLSyntaxError as e:
        print(f"❌ XML parsing error in {file_path.name}: {e}")
        return []

    nodes = []
    for section in root.findall("section"):
        version = section.attrib.get("version", "").strip()
        dimension = section.attrib.get("title", "").strip()
        rules = section.findall("rule")

        for rule in rules:
            rule_name = rule.attrib.get("name", "").strip()
            description_node = rule.find("description")
            description_text = description_node.text.strip() if description_node is not None and description_node.text else ""

            example_node = rule.find("example")
            code_blocks = []
            if example_node is not None:
                for block in example_node.iter():
                    if block.tag in ["goodCase", "badCase"] and block.text:
                        code_blocks.append(block.text.strip())

            if code_blocks:
                for code_text in code_blocks:
                    chunk_text = f"{description_text}\n\n{code_text}".strip()
                    nodes.append(TextNode(
                        text=chunk_text,
                        metadata={
                            "version": version,
                            "dimension": dimension,
                            "rule_name": rule_name,
                            "source_file": file_path.name
                        }
                    ))
            elif description_text:
                nodes.append(TextNode(
                    text=description_text,
                    metadata={
                        "version": version,
                        "dimension": dimension,
                        "rule_name": rule_name,
                        "source_file": file_path.name
                    }
                ))
    return nodes

# 將 chunk 轉換為 Markdown 格式
def turn_chunks_to_markdown(chunks: list[TextNode]) -> str:
    md_lines = []
    for chunk in chunks:
        rule_name = chunk.metadata.get("rule_name", "")
        version = chunk.metadata.get("version", "")
        dimension = chunk.metadata.get("dimension", "")
        source_file = chunk.metadata.get("source_file", "")

        md_lines.append(f"## {rule_name}")
        md_lines.append(f"- 維度：{dimension}")
        md_lines.append(f"- 版本：{version}")
        md_lines.append(f"- 來源：{source_file}")
        md_lines.append("")
        md_lines.append(chunk.text.strip())
        md_lines.append("\n---\n")

    return "\n".join(md_lines)

# 查詢現有文件名稱對應的 document_id
def get_existing_documents(dataset_id: str, api_key: str, base_url: str = DIFY_BASE_URL) -> dict:
    url = f"{base_url}/datasets/{dataset_id}/documents"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return {
            doc["name"].replace(".md", ""): doc["id"]
            for doc in response.json().get("data", [])
        }
    else:
        print(f"⚠️ 無法獲取知識庫文件列表：{response.status_code} {response.text}")
        return {}

# 上傳 markdown 文件 - 創建新文件
def create_markdown_to_dify(markdown_text: str, dataset_id: str, api_key: str, document_name: str):
    url = f"{DIFY_BASE_URL}/datasets/{dataset_id}/document/create-by-file"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp_file:
        tmp_file.write(markdown_text)
        tmp_file_path = tmp_file.name

    data = {
        "data": (None, json.dumps({
            "name": f"{document_name}.md",
            "indexing_technique": "high_quality",
            "process_rule": {
                "mode": "custom",
                "rules": {
                    "pre_processing_rules": [
                        {"id": "remove_extra_spaces", "enabled": True},
                        {"id": "remove_urls_emails", "enabled": True}
                    ],
                    "segmentation": {
                        "separator": "##",
                        "max_tokens": 1000,
                        "parent_mode": "paragraph"
                    }
                }
            }
        }), "application/json")
    }
    files = {
        "file": (f"{document_name}.md", open(tmp_file_path, "rb"), "text/markdown")
    }

    print(f"📤 使用 create-by-file 上傳 {document_name}.md 到 Dify...")
    response = requests.post(url, headers=headers, files=files, data=data)
    if response.status_code == 200:
        print(f"✅ 成功創建 {document_name}.md")
    else:
        print(f"❌ 創建失敗（{document_name}.md）：{response.status_code}，內容：{response.text}")

# 上傳 markdown 文件 - 更新已存在文件
def upload_markdown_to_dify(markdown_text: str, dataset_id: str, document_id: str, api_key: str, document_name: str):
    url = f"{DIFY_BASE_URL}/datasets/{dataset_id}/documents/{document_id}/update-by-file"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp_file:
        tmp_file.write(markdown_text)
        tmp_file_path = tmp_file.name

    data = {
        "data": (None, json.dumps({
            "name": f"{document_name}.md",
            "indexing_technique": "high_quality",
            "process_rule": {
                "mode": "custom",
                "rules": {
                    "pre_processing_rules": [
                        {"id": "remove_extra_spaces", "enabled": True},
                        {"id": "remove_urls_emails", "enabled": True}
                    ],
                    "segmentation": {
                        "separator": "##",
                        "max_tokens": 1000,
                        "parent_mode": "paragraph"
                    }
                }
            }
        }), "application/json")
    }
    files = {
        "file": (f"{document_name}.md", open(tmp_file_path, "rb"), "text/markdown")
    }

    print(f"📤 使用 update-by-file 上傳 {document_name}.md 到 Dify...")
    response = requests.post(url, headers=headers, files=files, data=data)
    if response.status_code == 200:
        print(f"✅ 成功更新 {document_name}.md")
    else:
        print(f"❌ 更新失敗（{document_name}.md）：{response.status_code}，內容：{response.text}")

# 讀每個 XML -> 切 chunks -> 轉 md -> 判斷是否上傳或創建
if __name__ == "__main__":
    existing_docs = get_existing_documents(DATASET_ID, DIFY_API_KEY)

    for file in XML_DIR.glob("*.xml"):
        print(f"\n📄 正在處理：{file.name}")
        chunks = parse_xml_file_to_nodes(file)
        if not chunks:
            print(f"⚠️ 跳過：{file.name}（無有效 chunks）")
            continue

        markdown = turn_chunks_to_markdown(chunks)
        document_name = file.stem

        if document_name in existing_docs:
            upload_markdown_to_dify(
                markdown_text=markdown,
                dataset_id=DATASET_ID,
                document_id=existing_docs[document_name],
                api_key=DIFY_API_KEY,
                document_name=document_name
            )
        else:
            create_markdown_to_dify(
                markdown_text=markdown,
                dataset_id=DATASET_ID,
                api_key=DIFY_API_KEY,
                document_name=document_name
            )
