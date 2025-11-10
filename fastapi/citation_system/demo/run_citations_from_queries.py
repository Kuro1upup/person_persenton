# scripts/run_citations_from_queries.py
import json
from pathlib import Path
import sys


# 添加项目路径
project_root = Path("/home/spiritai/wpx/fastapi/citation-system/")
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(level=logging.INFO)

from src.citation_generator import CitationGenerator
from config import DATA_DIR

def main():
    queries_file = DATA_DIR / "queries.jsonl"
    output_file = DATA_DIR / "citation_results.jsonl"

    if not queries_file.exists():
        raise FileNotFoundError(f"queries.jsonl 不存在: {queries_file}")

    gen = CitationGenerator()

    with open(queries_file, "r", encoding="utf-8") as fin, \
         open(output_file, "w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            q = json.loads(line)
            qtext = q["query"]
            k = q.get("top_k", 3)
            citations = gen.generate_citations(qtext, k=k)
            out = {
                "id": q.get("id"),
                "query": qtext,
                "citations": [c.to_dict() for c in citations]
            }
            fout.write(json.dumps(out, ensure_ascii=False) + "\n")

            # 同时输出到控制台
            print(f"[{q.get('id', 'unknown')}] {qtext} -> {len(citations)} citations")

    print(f"✅ 已生成引用结果: {output_file}")

if __name__ == "__main__":
    main()
