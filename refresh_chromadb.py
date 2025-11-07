#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick script to delete old data and re-upload with AI-powered metadata
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import from main app
from main import meeting_collection
from bulk_upload_to_chroma import bulk_upload_from_folder

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Delete old data and re-upload with AI metadata"""

    if not meeting_collection:
        logger.error("❌ ChromaDB collection not initialized")
        return

    # Get current count
    current_count = meeting_collection.count()
    logger.info(f"\n📊 Current documents in ChromaDB: {current_count}")

    if current_count > 0:
        # Delete all data
        logger.info(f"\n🗑️  Deleting {current_count} old documents...")
        all_data = meeting_collection.get()
        if all_data and all_data['ids']:
            meeting_collection.delete(ids=all_data['ids'])
            logger.info(f"✅ Deleted {len(all_data['ids'])} documents")

        # Verify deletion
        new_count = meeting_collection.count()
        logger.info(f"📊 New count: {new_count}")

    # Upload fresh data with AI-powered extraction
    logger.info("\n" + "="*80)
    logger.info("🚀 STARTING BULK UPLOAD WITH AI-POWERED METADATA EXTRACTION")
    logger.info("="*80)

    bulk_upload_from_folder("inputs")


if __name__ == "__main__":
    main()
