"""Merge the three legacy driving collections into a unified DRIVING collection.

This script works at the JSON level — it merges docstore, vector store,
and index store dicts without re-embedding or making any API calls.
It is designed to run *inside* the rag-service container.

Usage:
    python scripts/merge_driving_collections.py
"""

import json
import shutil
import uuid
from pathlib import Path

STORAGE = Path("/app/storage")
TARGET = STORAGE / "DRIVING"
SOURCES = [
    STORAGE / "DRIVING_Highway_Code",
    STORAGE / "DRIVING_Traffic_Rules_and_Regulations",
    STORAGE / "DRIVING_Provisional_License_Test_Prep",
]


def merge_dicts_deep(base: dict, addition: dict) -> dict:
    """Recursively merge `addition` into `base` (no key overwrite conflicts
    expected since node IDs are UUIDs)."""
    for key, val in addition.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            merge_dicts_deep(base[key], val)
        else:
            base[key] = val
    return base


def main():
    # Validate sources
    valid_sources: list[Path] = []
    for src in SOURCES:
        if (src / "index_store.json").exists():
            valid_sources.append(src)
            print(f"  ✅ Found valid index: {src.name}")
        else:
            print(f"  ⚠️  Skipping {src.name} — no index_store.json")

    if not valid_sources:
        print("❌ No valid source collections found. Aborting.")
        return

    # ── Wipe corrupted DRIVING if present ────────────────────────────────
    if TARGET.exists():
        print(f"  🗑️  Removing corrupted {TARGET.name}/")
        shutil.rmtree(TARGET)
    TARGET.mkdir(parents=True, exist_ok=True)

    # ── Merge JSON stores ────────────────────────────────────────────────
    merged_docstore: dict = {}
    merged_vector_store: dict = {}
    merged_image_vector_store: dict = {}
    merged_index_nodes: dict = {}  # all node_ids for the unified index

    total_nodes = 0

    for src in valid_sources:
        print(f"  📦 Merging {src.name}...")

        # Docstore
        with open(src / "docstore.json") as f:
            ds = json.load(f)
        if not merged_docstore:
            merged_docstore = ds
        else:
            # Merge ref_doc_info and data dicts
            for key in ["docstore/ref_doc_info", "docstore/data"]:
                if key in ds:
                    merged_docstore.setdefault(key, {})
                    merged_docstore[key].update(ds[key])
            # Merge metadata if present
            if "docstore/metadata" in ds:
                merged_docstore.setdefault("docstore/metadata", {})
                merge_dicts_deep(merged_docstore["docstore/metadata"], ds["docstore/metadata"])

        # Vector store
        with open(src / "default__vector_store.json") as f:
            vs = json.load(f)
        if not merged_vector_store:
            merged_vector_store = vs
        else:
            for key in ["embedding_dict", "text_id_to_ref_doc_id", "metadata_dict"]:
                if key in vs:
                    merged_vector_store.setdefault(key, {})
                    merged_vector_store[key].update(vs[key])

        node_count = len(vs.get("embedding_dict", {}))
        total_nodes += node_count
        print(f"      Nodes: {node_count}")

        # Image vector store
        img_vs_path = src / "image__vector_store.json"
        if img_vs_path.exists():
            with open(img_vs_path) as f:
                ivs = json.load(f)
            if not merged_image_vector_store:
                merged_image_vector_store = ivs
            else:
                for key in ["embedding_dict", "text_id_to_ref_doc_id", "metadata_dict"]:
                    if key in ivs:
                        merged_image_vector_store.setdefault(key, {})
                        merged_image_vector_store[key].update(ivs[key])

        # Collect all node IDs for the unified index entry
        # In LlamaIndex format, index entries have __type__ + __data__ (JSON string)
        # The nodes_dict is inside the parsed __data__
        with open(src / "index_store.json") as f:
            ix = json.load(f)
        idx_data = ix.get("index_store/data", {})
        for _index_id, index_info in idx_data.items():
            data_str = index_info.get("__data__", "{}")
            parsed_data = json.loads(data_str)
            nodes_dict = parsed_data.get("nodes_dict", {})
            merged_index_nodes.update(nodes_dict)

        # Copy images
        src_images = src / "images"
        target_images = TARGET / "images"
        if src_images.exists():
            target_images.mkdir(parents=True, exist_ok=True)
            for img in src_images.iterdir():
                if img.is_file():
                    shutil.copy2(img, target_images / img.name)

        # Copy image manifest if exists
        img_manifest = src / "image_manifest.json"
        if img_manifest.exists():
            target_manifest = TARGET / "image_manifest.json"
            if target_manifest.exists():
                # Merge manifests
                with open(target_manifest) as f:
                    existing = json.load(f)
                with open(img_manifest) as f:
                    new_data = json.load(f)
                if isinstance(existing, dict) and isinstance(new_data, dict):
                    existing.update(new_data)
                    with open(target_manifest, "w") as f:
                        json.dump(existing, f)
                elif isinstance(existing, list) and isinstance(new_data, list):
                    existing.extend(new_data)
                    with open(target_manifest, "w") as f:
                        json.dump(existing, f)
            else:
                shutil.copy2(img_manifest, target_manifest)

    # ── Write merged files ───────────────────────────────────────────────

    # Docstore
    with open(TARGET / "docstore.json", "w") as f:
        json.dump(merged_docstore, f)

    # Vector store  
    with open(TARGET / "default__vector_store.json", "w") as f:
        json.dump(merged_vector_store, f)

    # Image vector store
    with open(TARGET / "image__vector_store.json", "w") as f:
        json.dump(merged_image_vector_store if merged_image_vector_store else {
            "embedding_dict": {}, "text_id_to_ref_doc_id": {}, "metadata_dict": {}
        }, f)

    # Graph store (empty)
    with open(TARGET / "graph_store.json", "w") as f:
        json.dump({"graph_dict": {}}, f)

    # Index store — single unified index entry matching LlamaIndex format
    # Valid format: only __type__ + __data__ (JSON string)
    unified_index_id = str(uuid.uuid4())
    inner_data = {
        "index_id": unified_index_id,
        "summary": None,
        "nodes_dict": merged_index_nodes,
        "doc_id_dict": {},
        "embeddings_dict": {},
    }
    index_store = {
        "index_store/data": {
            unified_index_id: {
                "__type__": "vector_store",
                "__data__": json.dumps(inner_data),
            }
        }
    }
    with open(TARGET / "index_store.json", "w") as f:
        json.dump(index_store, f)

    print(f"\n🎉 Successfully merged {len(valid_sources)} collections into DRIVING/")
    print(f"   Total nodes: {total_nodes}")
    print(f"   Docstore entries: {len(merged_docstore.get('docstore/data', {}))}")
    print(f"   Embedding entries: {len(merged_vector_store.get('embedding_dict', {}))}")


if __name__ == "__main__":
    main()
