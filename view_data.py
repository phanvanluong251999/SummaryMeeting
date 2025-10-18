#!/usr/bin/env python3
"""
Script đơn giản để xem data trong ChromaDB
Sử dụng: python view_data.py
"""

import chromadb
import os
from datetime import datetime

# Colors cho terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    """In header với màu"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}\n")

def print_success(text):
    """In success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_warning(text):
    """In warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_error(text):
    """In error message"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def main():
    print_header("XEM DỮ LIỆU TRONG CHROMADB")
    
    # Kiểm tra thư mục ChromaDB
    if not os.path.exists("chroma_db"):
        print_error("Thư mục 'chroma_db' không tồn tại!")
        print(f"\n{Colors.YELLOW}Hướng dẫn:{Colors.END}")
        print("1. Chạy ứng dụng: python app/main.py")
        print("2. Mở browser: http://localhost:5000")
        print("3. Upload file và tạo summary")
        print("4. Chạy lại script này\n")
        return
    
    print_success("Thư mục ChromaDB tồn tại")
    
    try:
        # Kết nối đến ChromaDB
        print("\n📡 Đang kết nối đến ChromaDB...")
        client = chromadb.PersistentClient(path="chroma_db")
        print_success("Kết nối thành công")
        
        # Liệt kê collections
        collections = client.list_collections()
        print(f"\n📚 Số lượng collections: {len(collections)}")
        if collections:
            for col in collections:
                print(f"   - {col.name}")
        
        # Lấy collection meeting_summaries
        try:
            collection = client.get_collection(name="meeting_summaries")
            print_success("Tìm thấy collection 'meeting_summaries'")
        except Exception:
            print_error("Không tìm thấy collection 'meeting_summaries'")
            print("\n💡 Chưa có dữ liệu. Hãy tạo summary trong ứng dụng trước!\n")
            return
        
        # Đếm số lượng meetings
        count = collection.count()
        print(f"\n📊 Tổng số cuộc họp: {Colors.BOLD}{count}{Colors.END}")
        
        if count == 0:
            print_warning("Chưa có cuộc họp nào được lưu")
            print("\n💡 Để thêm cuộc họp:")
            print("1. Mở http://localhost:5000")
            print("2. Upload file (txt/pdf/mp3)")
            print("3. Click 'Tạo bản tóm tắt'")
            print("4. ✅ Data tự động lưu vào ChromaDB!\n")
            return
        
        # Lấy tất cả data
        print("\n🔍 Đang tải dữ liệu...")
        results = collection.get()
        
        # Hiển thị danh sách
        print_header("DANH SÁCH CUỘC HỌP")
        
        for i in range(len(results['ids'])):
            doc_id = results['ids'][i]
            meta = results['metadatas'][i]
            summary = results['documents'][i]
            
            # Lấy thông tin
            title = meta.get('title', 'Không có tiêu đề')
            date = meta.get('date', 'N/A')
            filename = meta.get('filename', 'N/A')
            created = meta.get('created_at', 'N/A')
            text_length = meta.get('text_length', 0)
            
            # In thông tin
            print(f"\n{Colors.BOLD}{i+1}. {title}{Colors.END}")
            print(f"   📅 Ngày: {date}")
            print(f"   📄 File: {filename}")
            print(f"   🕐 Tạo lúc: {created[:19] if created != 'N/A' else 'N/A'}")
            print(f"   📏 Độ dài tóm tắt: {len(summary)} ký tự")
            if text_length:
                print(f"   📝 Độ dài văn bản gốc: {text_length:,} ký tự")
            
            # Preview nội dung
            preview_length = 150
            preview = summary[:preview_length]
            if len(summary) > preview_length:
                preview += "..."
            
            print(f"\n   {Colors.YELLOW}Nội dung (preview):{Colors.END}")
            print(f"   {preview}")
            print(f"\n   {Colors.BLUE}{'─'*76}{Colors.END}")
        
        # Thống kê thêm
        print_header("THỐNG KÊ")
        
        # Đếm theo ngày
        from collections import defaultdict
        by_date = defaultdict(int)
        dates = []
        
        for meta in results['metadatas']:
            date = meta.get('date', 'Unknown')
            by_date[date] += 1
            dates.append(date)
        
        print(f"\n📅 Số ngày có cuộc họp: {len(by_date)}")
        print(f"\n   Phân bố theo ngày:")
        for date in sorted(by_date.keys(), reverse=True):
            count = by_date[date]
            bar = "█" * count
            print(f"   {date}: {bar} ({count})")
        
        # Tổng số ký tự
        total_chars = sum(len(doc) for doc in results['documents'])
        avg_chars = total_chars / count if count > 0 else 0
        
        print(f"\n📝 Tổng số ký tự: {total_chars:,}")
        print(f"📊 Trung bình: {avg_chars:.0f} ký tự/cuộc họp")
        
        # Cuộc họp mới nhất
        if results['metadatas']:
            latest_meta = results['metadatas'][-1]
            print(f"\n⏰ Cuộc họp mới nhất: {latest_meta.get('title', 'N/A')}")
            print(f"   📅 Ngày: {latest_meta.get('date', 'N/A')}")
        
        # Test search
        print_header("TEST SEMANTIC SEARCH")
        
        test_query = "budget planning"
        print(f"🔍 Tìm kiếm với query: '{test_query}'")
        
        search_results = collection.query(
            query_texts=[test_query],
            n_results=min(3, count)
        )
        
        if search_results['ids'] and search_results['ids'][0]:
            print_success(f"Tìm thấy {len(search_results['ids'][0])} kết quả:")
            for i, doc_id in enumerate(search_results['ids'][0]):
                meta = search_results['metadatas'][0][i]
                distance = search_results['distances'][0][i] if 'distances' in search_results else None
                relevance = (1 - distance) * 100 if distance is not None else 0
                
                print(f"\n   {i+1}. {meta.get('title', 'N/A')}")
                print(f"      📅 {meta.get('date', 'N/A')}")
                if distance is not None:
                    print(f"      🎯 Relevance: {relevance:.1f}%")
        else:
            print_warning("Không tìm thấy kết quả")
        
        # Hướng dẫn tiếp theo
        print_header("HƯỚNG DẪN SỬ DỤNG")
        print("\n💡 Bạn có thể:")
        print("   1. Tìm kiếm trong Chatbot trên web interface")
        print("   2. Sử dụng API: POST /search_meetings")
        print("   3. Xem danh sách: GET /list_meetings")
        print("   4. Chạy lại script này bất cứ lúc nào: python view_data.py")
        
        print(f"\n{Colors.GREEN}✅ Hoàn tất!{Colors.END}\n")
        
    except Exception as e:
        print_error(f"Lỗi: {e}")
        print(f"\n{Colors.YELLOW}Debug info:{Colors.END}")
        print(f"- Working directory: {os.getcwd()}")
        print(f"- ChromaDB path: {os.path.abspath('chroma_db')}")
        print(f"- Error type: {type(e).__name__}")
        print(f"\n💡 Thử chạy lại ứng dụng và tạo summary mới.\n")

if __name__ == "__main__":
    main()