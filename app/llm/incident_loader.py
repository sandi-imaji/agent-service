"""
CSV Incident Loader untuk RAG System
Mengubah data CSV incident menjadi Document yang bisa diindex
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional
from llama_index.core import Document
from app.config import Config


def load_incident_documents(csv_path: Optional[Path] = None) -> List[Document]:
    """
    Load incident CSV dan convert ke LlamaIndex Documents

    Returns:
        List[Document]: List of documents ready for indexing
    """
    if csv_path is None:
        csv_path = Config.dir / "storages" / "docs" / "incident_finish_2025.csv"

    if not csv_path.exists():
        print(f"[WARNING] CSV file not found: {csv_path}")
        return []

    # Read CSV
    df = pd.read_csv(csv_path)
    print(f"[INFO] Loaded {len(df)} incidents from CSV")

    documents = []

    for idx, row in df.iterrows():
        # Buat content yang rich dengan struktur yang jelas
        # Prioritaskan report_cause dan report_action sesuai permintaan user
        content_parts = []

        # Header dengan nama incident
        content_parts.append(f"# Incident: {row['name']}")
        content_parts.append(f"\n**Status**: {row['status']}")
        content_parts.append(f"**Level**: {row['level']}")
        content_parts.append(f"**Date**: {row['datetime']}")

        # Description
        if pd.notna(row["description"]) and str(row["description"]).strip():
            content_parts.append(f"\n## Description")
            content_parts.append(str(row["description"]))

        # Chronology
        if pd.notna(row["report_chronology"]) and str(row["report_chronology"]).strip():
            content_parts.append(f"\n## Chronology")
            content_parts.append(str(row["report_chronology"]))

        # ROOT CAUSE - Prioritas tinggi
        if pd.notna(row["report_cause"]) and str(row["report_cause"]).strip():
            content_parts.append(f"\n## Root Cause")
            content_parts.append(str(row["report_cause"]))

        # ACTION TAKEN - Prioritas tinggi
        if pd.notna(row["report_action"]) and str(row["report_action"]).strip():
            content_parts.append(f"\n## Action Taken")
            content_parts.append(str(row["report_action"]))

        # Result
        if pd.notna(row["report_result"]) and str(row["report_result"]).strip():
            content_parts.append(f"\n## Result")
            content_parts.append(str(row["report_result"]))

        # Corrective Action
        if (
            pd.notna(row["service_corrective"])
            and str(row["service_corrective"]).strip()
        ):
            content_parts.append(f"\n## Corrective Action")
            content_parts.append(str(row["service_corrective"]))

        # Preventive Action
        if (
            pd.notna(row["service_preventive"])
            and str(row["service_preventive"]).strip()
        ):
            content_parts.append(f"\n## Preventive Action")
            content_parts.append(str(row["service_preventive"]))

        # Gabungkan semua content
        content = "\n".join(content_parts)

        # Metadata untuk filtering dan retrieval
        metadata = {
            "source": "incident_csv",
            "incident_id": str(row["id"]),
            "incident_name": str(row["name"]),
            "status": str(row["status"]),
            "level": str(row["level"]),
            "datetime": str(row["datetime"]),
            "has_cause": pd.notna(row["report_cause"])
            and str(row["report_cause"]).strip() != "",
            "has_action": pd.notna(row["report_action"])
            and str(row["report_action"]).strip() != "",
            "doc_type": "incident",
        }

        # Extract site/location dari nama (e.g., [DCI], [DISM])
        name = str(row["name"])
        if "[" in name and "]" in name:
            site = name[name.find("[") + 1 : name.find("]")]
            metadata["site"] = site

        doc = Document(text=content, metadata=metadata)
        documents.append(doc)

    print(f"[INFO] Created {len(documents)} incident documents")
    return documents


if __name__ == "__main__":
    # Test loading
    docs = load_incident_documents()
    if docs:
        print(f"\n[TEST] Sample document:")
        print(f"Name: {docs[0].metadata['incident_name']}")
        print(f"Status: {docs[0].metadata['status']}")
        print(f"Content preview:\n{docs[0].text[:500]}...")
