#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clear all ChromaDB data
"""
import sys
sys.path.insert(0, 'E:/SummaryMeeting')

from main import meeting_collection

print("="*80)
print("CLEARING CHROMADB DATA")
print("="*80)

if not meeting_collection:
    print("❌ ChromaDB collection not available")
    sys.exit(1)

# Get current count
current_count = meeting_collection.count()
print(f"\nCurrent documents: {current_count}")

if current_count == 0:
    print("✅ ChromaDB is already empty!")
    sys.exit(0)

# Get all IDs
print("\nDeleting all documents...")
results = meeting_collection.get()
all_ids = results['ids']

# Delete all
meeting_collection.delete(ids=all_ids)

# Verify
remaining = meeting_collection.count()
print(f"\n✅ Successfully deleted {len(all_ids)} documents!")
print(f"Remaining documents: {remaining}")

print("\n" + "="*80)
