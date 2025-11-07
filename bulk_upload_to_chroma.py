#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bulk Upload Script for ChromaDB with AI-Powered Metadata Extraction
Processes all files from 'inputs' folder and uploads to ChromaDB (local or cloud)
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import re
from dotenv import load_dotenv
import uuid

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
load_dotenv()

# Import from main app
from main import (
    client,
    meeting_collection,
    extract_text,
    generate_meeting_title,
    Config,
    # NEW: Import updated metadata extraction functions
    extract_key_topics,
    extract_participants_with_roles,
    detect_language,
    extract_actual_duration,
    extract_individual_actions,
    detect_meeting_type
)

import json

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def extract_date_from_filename(filename: str) -> str:
    """Extract date from filename (e.g., meeting_kickoff_03102025.txt -> 2025-10-03)"""
    try:
        # Try to find date patterns in filename
        patterns = [
            r'(\d{8})',  # DDMMYYYY or YYYYMMDD
            r'(\d{1,2})[-_](\d{1,2})[-_](\d{4})',  # DD-MM-YYYY
            r'(\d{4})[-_](\d{1,2})[-_](\d{1,2})',  # YYYY-MM-DD
        ]

        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                if len(match.groups()) == 1:
                    # DDMMYYYY or YYYYMMDD
                    date_str = match.group(1)
                    if len(date_str) == 8:
                        # Try DDMMYYYY first
                        try:
                            day = int(date_str[:2])
                            month = int(date_str[2:4])
                            year = int(date_str[4:8])
                            if 1 <= day <= 31 and 1 <= month <= 12:
                                return f"{year:04d}-{month:02d}-{day:02d}"
                        except:
                            pass
                        # Try YYYYMMDD
                        try:
                            year = int(date_str[:4])
                            month = int(date_str[4:6])
                            day = int(date_str[6:8])
                            if 1 <= day <= 31 and 1 <= month <= 12:
                                return f"{year:04d}-{month:02d}-{day:02d}"
                        except:
                            pass
                elif len(match.groups()) == 3:
                    # Check if YYYY-MM-DD or DD-MM-YYYY
                    if len(match.group(1)) == 4:
                        # YYYY-MM-DD
                        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
                    else:
                        # DD-MM-YYYY
                        return f"{match.group(3)}-{int(match.group(2)):02d}-{int(match.group(1)):02d}"

        # Fallback to current date
        return datetime.now().strftime("%Y-%m-%d")
    except Exception as e:
        logger.error(f"Error extracting date from filename: {e}")
        return datetime.now().strftime("%Y-%m-%d")


def save_to_chromadb_with_new_metadata(
    summary: str,
    title: str,
    date: str,
    original_text: str,
    filename: str
) -> bool:
    """
    Save to ChromaDB with NEW enhanced metadata structure (v2)
    Uses the same metadata extraction as main.py

    Args:
        summary: Meeting summary
        title: Meeting title
        date: Meeting date
        original_text: Original meeting text
        filename: Original filename

    Returns:
        bool: Success status
    """
    try:
        if not meeting_collection:
            logger.warning("ChromaDB collection not available")
            return False

        # ⭐ SAME METADATA EXTRACTION AS main.py
        logger.info("  🤖 Extracting enhanced metadata...")

        # Extract comprehensive metadata focused on people and actions
        topics = extract_key_topics(summary)
        participants_with_roles = extract_participants_with_roles(original_text, summary)
        language = detect_language(original_text)
        duration_info = extract_actual_duration(original_text, summary)
        individual_actions = extract_individual_actions(summary, original_text)
        meeting_type = detect_meeting_type(summary, original_text)

        # Format participants for storage
        participants_str = ", ".join([p["name"] for p in participants_with_roles])
        participant_roles = {p["name"]: p["role"] for p in participants_with_roles if p["role"]}

        # Format actions for storage
        actions_summary = []
        for action in individual_actions:
            action_str = f"{action['person']}: {action['action']}"
            if action.get('deadline'):
                action_str += f" (deadline: {action['deadline']})"
            actions_summary.append(action_str)

        # ⭐ NEW METADATA STRUCTURE: Focused on time, people, and individual actions
        timestamp = int(datetime.now().timestamp())
        unique_id = str(uuid.uuid4())[:8]
        safe_filename = filename.replace('.txt', '')
        doc_id = f"{date}_{timestamp}_{unique_id}_{safe_filename}"

        # ⭐ FIX: Ensure all metadata values are ChromaDB-compatible types (bool, int, float, str)
        # ChromaDB doesn't accept None or empty strings in some fields
        metadata = {
            # === Basic Information ===
            "title": str(title),
            "date": str(date),
            "filename": str(filename),
            "created_at": datetime.now().isoformat(),

            # === Meeting Classification ===
            "meeting_type": str(meeting_type),
            "language": str(language),

            # === Time Information (NEW - IMPROVED) ===
            "duration_minutes": int(duration_info["minutes"]),
            "duration_source": str(duration_info["source"]),
            # ChromaDB fix: Use "N/A" instead of empty string
            "start_time": str(duration_info.get("start_time") or "N/A"),
            "end_time": str(duration_info.get("end_time") or "N/A"),
            "is_short_meeting": bool(duration_info["minutes"] < 30),
            "is_long_meeting": bool(duration_info["minutes"] > 90),

            # === People & Participation (NEW - IMPROVED) ===
            "participants": str(participants_str) if participants_str else "N/A",
            "participant_count": int(len(participants_with_roles)),
            "participant_roles": str(json.dumps(participant_roles, ensure_ascii=False)),
            "has_multiple_speakers": bool(len(participants_with_roles) > 2),

            # === Individual Actions (NEW - KEY FEATURE) ===
            "individual_actions": str(" | ".join(actions_summary)) if actions_summary else "N/A",
            "action_count": int(len(individual_actions)),
            "has_actions": bool(len(individual_actions) > 0),

            # === Content Metrics ===
            "text_length": int(len(original_text)),
            "summary_length": int(len(summary)),
            "word_count": int(len(original_text.split())),
            "topics": str(", ".join(topics)) if topics else "N/A",
        }

        logger.info(f"  📋 Enhanced Metadata Extracted:")
        logger.info(f"     🏷️  Type: {meeting_type}")
        logger.info(f"     📊 Topics: {topics}")
        logger.info(f"     👥 Participants ({len(participants_with_roles)}): {[p['name'] for p in participants_with_roles]}")
        logger.info(f"     🌐 Language: {language}")
        logger.info(f"     ⏱️  Duration: {duration_info['minutes']} min (source: {duration_info['source']})")
        if duration_info.get("start_time"):
            logger.info(f"     🕐 Time: {duration_info['start_time']} - {duration_info['end_time']}")
        logger.info(f"     📝 Individual actions: {len(individual_actions)}")

        # Save to ChromaDB
        meeting_collection.add(
            documents=[summary],
            metadatas=[metadata],
            ids=[doc_id]
        )

        logger.info(f"  ✅ Successfully saved to ChromaDB!")
        logger.info(f"     Document ID: {doc_id}")

        return True

    except Exception as e:
        logger.error(f"  ❌ Error saving to ChromaDB: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def bulk_upload_from_folder(folder_path: str = "inputs"):
    """
    Bulk upload all text files from a folder to ChromaDB

    Args:
        folder_path: Path to folder containing meeting files
    """

    logger.info("="*80)
    logger.info("BULK UPLOAD TO CHROMADB")
    logger.info("="*80)

    # Check if folder exists
    if not os.path.exists(folder_path):
        logger.error(f"Folder not found: {folder_path}")
        return

    # Get all text files
    text_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]

    if not text_files:
        logger.warning(f"No .txt files found in {folder_path}")
        return

    logger.info(f"\nFound {len(text_files)} text files in '{folder_path}'")
    logger.info("-"*80)

    # Process each file
    success_count = 0
    error_count = 0

    for idx, filename in enumerate(text_files, 1):
        try:
            file_path = os.path.join(folder_path, filename)

            logger.info(f"\n[{idx}/{len(text_files)}] Processing: {filename}")

            # Extract text
            text = extract_text(file_path)
            if not text:
                logger.error(f"  ❌ Failed to extract text from {filename}")
                error_count += 1
                continue

            logger.info(f"  ✅ Extracted {len(text)} characters")

            # Extract date from filename
            date = extract_date_from_filename(filename)
            logger.info(f"  📅 Date: {date}")

            # Generate summary using AI with IMPROVED PROMPT
            logger.info(f"  🤖 Generating summary...")

            # Detect language for appropriate prompting
            is_vietnamese = detect_language(text) == "vi"

            if is_vietnamese:
                summary_prompt = f"""
Bạn là trợ lý tóm tắt cuộc họp chuyên nghiệp. Hãy phân tích biên bản cuộc họp sau và tạo bản tóm tắt CHI TIẾT theo cấu trúc sau:

**QUAN TRỌNG: Tập trung vào 3 yếu tố chính:**
1. THỜI GIAN: Thời lượng cuộc họp, thời gian bắt đầu/kết thúc (nếu có)
2. NGƯỜI THAM GIA: Danh sách đầy đủ người tham gia với vai trò/chức danh của họ
3. NHIỆM VỤ CỤ THỂ: Ai phụ trách làm gì, deadline (nếu có)

**CẤU TRÚC TÓM TẮT:**

## 1. Thông Tin Cuộc Họp
- Thời gian: [Ghi rõ thời gian bắt đầu - kết thúc, hoặc thời lượng cuộc họp]
- Người tham gia: [Liệt kê TẤT CẢ người tham gia với vai trò, ví dụ: "Dev A (Developer), PM Nam (Project Manager)"]

## 2. Nội Dung Chính
[Tóm tắt các nội dung thảo luận quan trọng, 3-5 điểm chính]

## 3. Phân Công Công Việc
[Liệt kê CHI TIẾT ai làm gì, theo format:]
- **[Tên người]** ([Vai trò]): [Nhiệm vụ cụ thể] - Deadline: [nếu có]
- **[Tên người]** ([Vai trò]): [Nhiệm vụ cụ thể] - Deadline: [nếu có]

**LƯU Ý QUAN TRỌNG:**
- Phải ghi CHÍNH XÁC tên người và vai trò như trong biên bản
- KHÔNG được nhầm lẫn giữa các người (ví dụ: Dev A ≠ Dev B)
- Mỗi nhiệm vụ phải ghi rõ ai chịu trách nhiệm
- Trích xuất thời gian/deadline nếu có đề cập
- Sử dụng ngôn ngữ tiếng Việt tự nhiên, rõ ràng

Biên bản cuộc họp:
{text}
"""
            else:
                summary_prompt = f"""
You are a professional meeting summarizer. Analyze the following meeting transcript and create a DETAILED summary with this structure:

**FOCUS ON 3 KEY ELEMENTS:**
1. TIME: Meeting duration, start/end time (if available)
2. PARTICIPANTS: Complete list of participants with their roles/titles
3. SPECIFIC TASKS: Who is responsible for what, with deadlines (if any)

**SUMMARY STRUCTURE:**

## 1. Meeting Information
- Time: [Note start - end time, or meeting duration]
- Participants: [List ALL participants with roles, e.g., "Dev A (Developer), PM John (Project Manager)"]

## 2. Key Discussion Points
[Summarize important discussion topics, 3-5 main points]

## 3. Task Assignments
[List DETAILED assignments using this format:]
- **[Person name]** ([Role]): [Specific task] - Deadline: [if available]
- **[Person name]** ([Role]): [Specific task] - Deadline: [if available]

**IMPORTANT NOTES:**
- Must record names and roles EXACTLY as in the transcript
- DO NOT confuse between people (e.g., Dev A ≠ Dev B)
- Each task must clearly state who is responsible
- Extract time/deadline information if mentioned
- Use clear, natural language

Meeting transcript:
{text}
"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant specialized in summarizing meeting notes."},
                    {"role": "user", "content": summary_prompt}
                ],
                temperature=0
            )

            summary = response.choices[0].message.content.strip()
            logger.info(f"  ✅ Summary generated ({len(summary)} chars)")

            # Generate title
            title = generate_meeting_title(text)
            logger.info(f"  📌 Title: {title}")

            # Save to ChromaDB with NEW enhanced metadata
            logger.info(f"  💾 Saving to ChromaDB with enhanced metadata...")
            success = save_to_chromadb_with_new_metadata(
                summary=summary,
                title=title,
                date=date,
                original_text=text,
                filename=filename
            )

            if success:
                logger.info(f"  ✅ Successfully uploaded!")
                success_count += 1
            else:
                logger.error(f"  ❌ Failed to save to ChromaDB")
                error_count += 1

        except Exception as e:
            logger.error(f"  ❌ Error processing {filename}: {e}")
            error_count += 1
            continue

    # Summary
    logger.info("\n" + "="*80)
    logger.info("UPLOAD COMPLETE")
    logger.info("="*80)
    logger.info(f"\n✅ Successful: {success_count}/{len(text_files)}")
    logger.info(f"❌ Failed: {error_count}/{len(text_files)}")

    if meeting_collection:
        total_docs = meeting_collection.count()
        logger.info(f"\n📊 Total documents in ChromaDB: {total_docs}")

    logger.info("\n" + "="*80)


def main():
    """Main function"""

    if not client:
        logger.error("❌ OpenAI client not initialized. Check your .env configuration.")
        return

    if not meeting_collection:
        logger.error("❌ ChromaDB collection not initialized. Check your ChromaDB configuration.")
        return

    # Get ChromaDB mode
    chroma_mode = os.environ.get('CHROMA_MODE', 'local')
    logger.info(f"\n🗄️  ChromaDB Mode: {chroma_mode.upper()}")

    if chroma_mode == 'cloud':
        chroma_host = os.environ.get('CHROMA_HOST', 'localhost')
        chroma_port = os.environ.get('CHROMA_PORT', '8000')
        logger.info(f"🌐 ChromaDB Server: {chroma_host}:{chroma_port}")
    else:
        logger.info(f"💾 ChromaDB Path: {Config.CHROMA_DIR}")

    # Check current document count
    current_count = meeting_collection.count()
    logger.info(f"\n📊 Current documents in ChromaDB: {current_count}")

    if current_count > 0:
        # Use ASCII for Windows compatibility
        print(f"\nWARNING: ChromaDB already has {current_count} documents.")
        response = input("Continue uploading? This will ADD to existing data (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Upload cancelled.")
            return

    # Start bulk upload
    bulk_upload_from_folder("inputs")


if __name__ == "__main__":
    main()
