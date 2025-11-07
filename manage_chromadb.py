#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChromaDB Data Management Tool
Helps view, delete, and manage your meeting data
"""

import chromadb
import os
import sys
from datetime import datetime
from chromadb.utils import embedding_functions

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def print_separator(char='=', length=80):
    """Print separator line"""
    print(char * length)


def get_collection():
    """Get ChromaDB collection"""
    try:
        client = chromadb.PersistentClient(path="chroma_db")

        # Use same embedding function as main app
        openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_base="https://aiportalapi.stu-platform.live/jpe",
            api_key="sk-GRpLsKVWmd1jVxaI7yssZA",
            model_name="text-embedding-3-small"
        )

        collection = client.get_collection(
            name="meeting_summaries",
            embedding_function=openai_ef
        )
        return collection
    except Exception as e:
        print(f"Error connecting to ChromaDB: {e}")
        return None


def view_all_data():
    """View all documents in ChromaDB with detailed metadata"""
    print_separator()
    print("VIEW ALL DATA IN CHROMADB")
    print_separator()

    collection = get_collection()
    if not collection:
        return

    count = collection.count()
    print(f"\nTotal documents: {count}\n")

    if count == 0:
        print("No documents found!")
        return

    results = collection.get()

    for i in range(len(results['ids'])):
        doc_id = results['ids'][i]
        meta = results['metadatas'][i] if results['metadatas'] else {}
        doc = results['documents'][i] if results['documents'] else ""

        print(f"\n[{i+1}] ID: {doc_id}")
        print(f"    📌 Title: {meta.get('title', 'N/A')}")
        print(f"    📅 Date: {meta.get('date', 'N/A')}")
        print(f"    🏷️  Type: {meta.get('meeting_type', 'N/A')}")
        print(f"    🌐 Language: {meta.get('language', 'N/A')}")

        # === Time Information (NEW) ===
        duration_min = meta.get('duration_minutes', 0)
        duration_source = meta.get('duration_source', 'unknown')
        start_time = meta.get('start_time', '')
        end_time = meta.get('end_time', '')

        if start_time and end_time:
            print(f"    ⏱️  Duration: {duration_min} min ({start_time} - {end_time}) [{duration_source}]")
        else:
            print(f"    ⏱️  Duration: {duration_min} min [{duration_source}]")

        # === Participants (NEW) ===
        print(f"    👥 Participants ({meta.get('participant_count', 0)}): {meta.get('participants', 'N/A')}")

        # Show participant roles if available
        participant_roles = meta.get('participant_roles', '')
        if participant_roles and participant_roles != '{}':
            try:
                import json
                roles_dict = json.loads(participant_roles)
                if roles_dict:
                    roles_str = ", ".join([f"{name} ({role})" for name, role in roles_dict.items()])
                    print(f"       Roles: {roles_str}")
            except:
                pass

        # === Individual Actions (NEW) ===
        individual_actions = meta.get('individual_actions', '')
        action_count = meta.get('action_count', 0)
        if individual_actions:
            print(f"    📝 Actions ({action_count}):")
            for action_str in individual_actions.split(' | ')[:3]:  # Show first 3 actions
                print(f"       • {action_str}")
            if action_count > 3:
                print(f"       ... and {action_count - 3} more")
        else:
            print(f"    📝 Actions: None")

        # === Content Metrics ===
        print(f"    📊 Text Length: {meta.get('text_length', 0)} chars")
        print(f"    📄 Summary Length: {len(doc)} chars")
        print(f"    🕐 Created: {meta.get('created_at', 'N/A')[:19]}")

        # Show preview of document (what's actually searched)
        print(f"\n    DOCUMENT CONTENT (first 200 chars):")
        print(f"    {doc[:200]}...")
        print_separator('-', 80)


def delete_all_data():
    """Delete all documents from ChromaDB"""
    print_separator()
    print("DELETE ALL DATA")
    print_separator()

    collection = get_collection()
    if not collection:
        return

    count = collection.count()
    print(f"\nCurrent documents: {count}")

    if count == 0:
        print("No documents to delete!")
        return

    # Confirm deletion
    confirm = input(f"\nAre you sure you want to delete ALL {count} documents? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Deletion cancelled.")
        return

    try:
        # Get all IDs
        results = collection.get()
        all_ids = results['ids']

        # Delete all
        collection.delete(ids=all_ids)

        print(f"\n✅ Successfully deleted {len(all_ids)} documents!")
        print(f"Remaining documents: {collection.count()}")

    except Exception as e:
        print(f"❌ Error deleting data: {e}")


def delete_by_id():
    """Delete specific document by ID"""
    print_separator()
    print("DELETE BY ID")
    print_separator()

    collection = get_collection()
    if not collection:
        return

    # Show all documents first
    results = collection.get()

    print("\nAvailable documents:\n")
    for i, doc_id in enumerate(results['ids']):
        meta = results['metadatas'][i]
        print(f"[{i+1}] {doc_id}")
        print(f"    Title: {meta.get('title', 'N/A')}, Date: {meta.get('date', 'N/A')}")

    # Get ID to delete
    doc_id = input("\nEnter document ID to delete: ").strip()

    if not doc_id:
        print("No ID provided. Cancelled.")
        return

    try:
        collection.delete(ids=[doc_id])
        print(f"\n✅ Successfully deleted document: {doc_id}")
        print(f"Remaining documents: {collection.count()}")
    except Exception as e:
        print(f"❌ Error: {e}")


def delete_by_date():
    """Delete all documents from a specific date"""
    print_separator()
    print("DELETE BY DATE")
    print_separator()

    collection = get_collection()
    if not collection:
        return

    # Show available dates
    results = collection.get()
    dates = set()
    for meta in results['metadatas']:
        if meta and 'date' in meta:
            dates.add(meta['date'])

    print("\nAvailable dates:\n")
    for date in sorted(dates):
        count = sum(1 for m in results['metadatas'] if m.get('date') == date)
        print(f"  {date} ({count} documents)")

    # Get date to delete
    target_date = input("\nEnter date to delete (YYYY-MM-DD): ").strip()

    if not target_date:
        print("No date provided. Cancelled.")
        return

    # Find IDs for this date
    ids_to_delete = []
    for i, meta in enumerate(results['metadatas']):
        if meta.get('date') == target_date:
            ids_to_delete.append(results['ids'][i])

    if not ids_to_delete:
        print(f"No documents found for date: {target_date}")
        return

    print(f"\nFound {len(ids_to_delete)} documents for {target_date}")
    confirm = input(f"Delete all {len(ids_to_delete)} documents? (yes/no): ")

    if confirm.lower() != 'yes':
        print("Deletion cancelled.")
        return

    try:
        collection.delete(ids=ids_to_delete)
        print(f"\n✅ Successfully deleted {len(ids_to_delete)} documents from {target_date}")
        print(f"Remaining documents: {collection.count()}")
    except Exception as e:
        print(f"❌ Error: {e}")


def check_structure():
    """Check what's being stored in documents vs metadata"""
    print_separator()
    print("DATA STRUCTURE ANALYSIS")
    print_separator()

    collection = get_collection()
    if not collection:
        return

    results = collection.get()

    if not results['ids']:
        print("No documents found!")
        return

    print("\n=== WHAT CHROMADB SEARCHES ===")
    print("\nChromaDB creates embeddings and searches on the 'documents' field.")
    print("Metadata is used for FILTERING, not for semantic search.\n")

    # Analyze first document
    doc = results['documents'][0]
    meta = results['metadatas'][0]

    print(f"\nExample Document #{1}:")
    print(f"  ID: {results['ids'][0]}")
    print(f"\n  📄 DOCUMENT (searched semantically):")
    print(f"     Length: {len(doc)} characters")
    print(f"     Content: {doc[:300]}...")

    print(f"\n  🏷️  METADATA (used for filtering):")
    for key, value in meta.items():
        print(f"     {key}: {value}")

    print("\n" + "="*80)
    print("RECOMMENDATION:")
    print("="*80)
    print("""
Your current structure is CORRECT:
✅ Documents field: Contains the SUMMARY (good for semantic search)
✅ Metadata fields: Enhanced with time, people, and actions data

NEW METADATA STRUCTURE (v2):
- duration_minutes, duration_source, start_time, end_time
- participants, participant_count, participant_roles (JSON)
- individual_actions (person: task with deadline)
- meeting_type, language, topics

ChromaDB semantic search works on the summary text, which is what you want.
The metadata provides rich filtering and context for the chatbot.

If search results are poor, the issue is likely:
1. Summaries are too generic (need more detail)
2. Old data with outdated metadata (priority, has_decisions, etc.)
3. Query phrasing doesn't match summary content

Solution: Delete old data and re-upload with the new metadata structure.
You can use the new summarization prompt which focuses on:
- TIME: Actual duration and meeting times
- PEOPLE: Participants with their roles
- ACTIONS: Individual tasks per person with deadlines
""")


def main():
    """Main menu"""
    while True:
        print_separator()
        print("CHROMADB MANAGEMENT TOOL")
        print_separator()
        print("\n1. View all data (with metadata)")
        print("2. Check data structure")
        print("3. Delete all data")
        print("4. Delete by ID")
        print("5. Delete by date")
        print("6. Exit")

        choice = input("\nEnter choice (1-6): ").strip()

        if choice == '1':
            view_all_data()
        elif choice == '2':
            check_structure()
        elif choice == '3':
            delete_all_data()
        elif choice == '4':
            delete_by_id()
        elif choice == '5':
            delete_by_date()
        elif choice == '6':
            print("\nGoodbye!")
            break
        else:
            print("\nInvalid choice. Try again.")

        input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
