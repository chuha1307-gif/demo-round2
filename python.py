import streamlit as st
import pandas as pd
from google import genai
from google.genai.errors import APIError

# --- Cấu hình Trang Streamlit ---
st.set_page_config(
    page_title="App Phân Tích Báo Cáo Tài Chính",
    layout="wide"
)

st.title("Ứng dụng Phân Tích Báo Cáo Tài Chính 📊")

# --- Khởi tạo Lịch sử Chat (Session State) ---
# Sử dụng một khóa riêng biệt cho chatbox tương tác
if "financial_messages" not in st.session_state:
    st.session_state.financial_messages = [
        {"role": "model", "content": "Xin chào! Sau khi bạn tải file Excel, tôi sẽ sẵn lòng trả lời các câu hỏi chuyên sâu về dữ liệu tài chính đã được phân tích."}
    ]

# --- Hàm tính toán chính (Sử dụng Caching để Tối ưu hiệu suất) ---
@st.cache_data
def process_financial_data(df):
    """Thực hiện các phép tính Tăng trưởng và Tỷ trọng."""
    
    # Đảm bảo các giá trị là số để tính toán
    numeric_cols = ['Năm trước', 'Năm sau']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 1. Tính Tốc độ Tăng trưởng
    # Dùng .replace(0, 1e-9) cho Series Pandas để tránh lỗi chia cho 0
    df['Tốc độ tăng trưởng (%)'] = (
        (df['Năm sau'] - df['Năm trước']) / df['Năm trước'].replace(0, 1e-9)
    ) * 100

    # 2. Tính Tỷ trọng theo Tổng Tài sản
    # Lọc chỉ tiêu "TỔNG CỘNG TÀI SẢN"
    tong_tai_san_row = df[df['Chỉ tiêu'].str.contains('TỔNG CỘNG TÀI SẢN', case=False, na=False)]
    
    if tong_tai_san_row.empty:
        raise ValueError("Không tìm thấy chỉ tiêu 'TỔNG CỘNG TỔNG TÀI SẢN'.")

    tong_tai_san_N_1 = tong_tai_san_row['Năm trước'].iloc[0]
    tong_tai_san_N = tong_tai_san_row['Năm sau'].iloc[0]

    # Xử lý giá trị 0 thủ công cho mẫu số để tránh lỗi chia cho 0
    divisor_N_1 = tong_tai_san_N_1 if tong_tai_san_N_1 != 0 else 1e-9
    divisor_N = tong_tai_san_N if tong_tai_san_N != 0 else 1e-9

    # Tính tỷ trọng với mẫu số đã được xử lý
    df['Tỷ trọng Năm trước (%)'] = (df['Năm trước'] / divisor_N_1) * 100
    df['Tỷ trọng Năm sau (%)'] = (df['Năm sau'] / divisor_N) * 100
    
    return df

# --- Hàm gọi API Gemini (Dùng cho Chức năng 5: Nhận xét button) ---
def get_ai_analysis(data_for_ai, api_key):
    """Gửi dữ liệu phân tích đến Gemini API và nhận nhận xét."""
    try:
        # Khởi tạo client tại đây vì st.secrets chỉ có thể truy cập bên trong các hàm streamlit/callback
        client = genai.Client(api_key=api_key)
        model_name = 'gemini-2.5-flash' 

        prompt = f"""
        Bạn là một chuyên gia phân tích tài chính chuyên nghiệp. Dựa trên các chỉ số tài chính sau, hãy đưa ra một nhận xét khách quan, ngắn gọn (khoảng 3-4 đoạn) về tình hình tài chính của doanh nghiệp. Đánh giá tập trung vào tốc độ tăng trưởng, thay đổi cơ cấu tài sản và khả năng thanh toán hiện hành.
        
        Dữ liệu thô và chỉ số:
        {data_for_ai}
        """

        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        return response.text

    except APIError as e:
        return f"Lỗi gọi Gemini API: Vui lòng kiểm tra Khóa API hoặc giới hạn sử dụng. Chi tiết lỗi: {e}"
    except Exception as e:
        return f"Đã xảy ra lỗi không xác định: {e}"


# --- Chức năng 1: Tải File ---
uploaded_file = st.file_uploader(
    "1. Tải file Excel Báo cáo Tài chính (Chỉ tiêu | Năm trước | Năm sau)",
    type=['xlsx', 'xls']
)

# Khởi tạo biến để giữ dữ liệu đã xử lý ngoài scope của if/else
df_processed = None
thanh_toan_hien_hanh_N = "N/A"
thanh_toan_hien_hanh_N_1 = "N/A"

if uploaded_file is not None:
    try:
        df_raw = pd.read_excel(uploaded_file)
        
        # Tiền xử lý: Đảm bảo chỉ có 3 cột quan trọng
        df_raw.columns = ['Chỉ tiêu', 'Năm trước', 'Năm sau']
        
        # Xử lý dữ liệu
        df_processed = process_financial_data(df_raw.copy())

        if df_processed is not None:
            
            # --- Chức năng 2 & 3: Hiển thị Kết quả ---
            st.subheader("2. Tốc độ Tăng trưởng & 3. Tỷ trọng Cơ cấu Tài sản")
            st.dataframe(df_processed.style.format({
                'Năm trước': '{:,.0f}',
                'Năm sau': '{:,.0f}',
                'Tốc độ tăng trưởng (%)': '{:.2f}%',
                'Tỷ trọng Năm trước (%)': '{:.2f}%',
                'Tỷ trọng Năm sau (%)': '{:.2f}%'
            }), use_container_width=True)
            
            # --- Chức năng 4: Tính Chỉ số Tài chính ---
            st.subheader("4. Các Chỉ số Tài chính Cơ bản")
            
            try:
                # Lấy Tài sản ngắn hạn
                tsnh_n = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
                tsnh_n_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

                # Lấy Nợ ngắn hạn
                no_ngan_han_N = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]  
                no_ngan_han_N_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

                # Tính toán, tránh chia cho 0
                thanh_toan_hien_hanh_N = (tsnh_n / no_ngan_han_N) if no_ngan_han_N != 0 else float('inf')
                thanh_toan_hien_hanh_N_1 = (tsnh_n_1 / no_ngan_han_N_1) if no_ngan_han_N_1 != 0 else float('inf')
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        label="Chỉ số Thanh toán Hiện hành (Năm trước)",
                        value=f"{thanh_toan_hien_hanh_N_1:.2f} lần" if thanh_toan_hien_hanh_N_1 != float('inf') else "Không xác định"
                    )
                with col2:
                    st.metric(
                        label="Chỉ số Thanh toán Hiện hành (Năm sau)",
                        value=f"{thanh_toan_hien_hanh_N:.2f} lần" if thanh_toan_hien_hanh_N != float('inf') else "Không xác định",
                        delta=f"{thanh_toan_hien_hanh_N - thanh_toan_hien_hanh_N_1:.2f}" if thanh_toan_hien_hanh_N != float('inf') and thanh_toan_hien_hanh_N_1 != float('inf') else None
                    )
                    
            except IndexError:
                 st.warning("Thiếu chỉ tiêu 'TÀI SẢN NGẮN HẠN' hoặc 'NỢ NGẮN HẠN' để tính chỉ số.")
            except ZeroDivisionError:
                 st.warning("Không thể tính Chỉ số Thanh toán Hiện hành do Nợ Ngắn Hạn bằng 0.")
                 
            # --- Chức năng 5: Nhận xét AI (Button) ---
            st.subheader("5. Nhận xét Tình hình Tài chính (AI - Button)")
            
            # Chuẩn bị dữ liệu để gửi cho AI
            data_for_ai = pd.DataFrame({
                'Chỉ tiêu': [
                    'Toàn bộ Bảng phân tích (dữ liệu thô)', 
                    'Tăng trưởng Tài sản ngắn hạn (%)', 
                    'Thanh toán hiện hành (N-1)', 
                    'Thanh toán hiện hành (N)'
                ],
                'Giá trị': [
                    df_processed.to_markdown(index=False),
                    f"{df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Tốc độ tăng trưởng (%)'].iloc[0]:.2f}%" if not df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)].empty else "N/A",
                    f"{thanh_toan_hien_hanh_N_1:.2f}" if isinstance(thanh_toan_hien_hanh_N_1, float) and thanh_toan_hien_hanh_N_1 != float('inf') else "N/A", 
                    f"{thanh_toan_hien_hanh_N:.2f}" if isinstance(thanh_toan_hien_hanh_N, float) and thanh_toan_hien_hanh_N != float('inf') else "N/A"
                ]
            }).to_markdown(index=False) 

            if st.button("Yêu cầu AI Phân tích"):
                api_key = st.secrets.get("GEMINI_API_KEY") 
                
                if api_key:
                    with st.spinner('Đang gửi dữ liệu và chờ Gemini phân tích...'):
                        ai_result = get_ai_analysis(data_for_ai, api_key)
                        st.markdown("**Kết quả Phân tích từ Gemini AI:**")
                        st.info(ai_result)
                else:
                     st.error("Lỗi: Không tìm thấy Khóa API. Vui lòng cấu hình Khóa 'GEMINI_API_KEY' trong Streamlit Secrets.")

    except ValueError as ve:
        st.error(f"Lỗi cấu trúc dữ liệu: {ve}")
    except Exception as e:
        st.error(f"Có lỗi xảy ra khi đọc hoặc xử lý file: {e}. Vui lòng kiểm tra định dạng file.")

    # --- CHỨC NĂNG 6: KHUNG CHAT TƯƠNG TÁC BÊN LỀ (MỚI) ---
    
    st.sidebar.header("Trò chuyện Chuyên sâu (Gemini)")
    st.sidebar.markdown("Hỏi AI các câu hỏi cụ thể về dữ liệu đã tải (Tăng trưởng, Tỷ trọng, Chỉ số).")

    # Hiển thị lịch sử chat
    for message in st.session_state.financial_messages:
        with st.sidebar.chat_message(message["role"]):
            st.markdown(message["content"])

    # Xử lý đầu vào chat
    if prompt := st.sidebar.chat_input("Hỏi AI về dữ liệu này...", key="chat_input_sidebar"):
        
        # 1. Thêm tin nhắn người dùng vào lịch sử
        st.session_state.financial_messages.append({"role": "user", "content": prompt})
        with st.sidebar.chat_message("user"):
            st.markdown(prompt)

        # 2. Xây dựng Ngữ cảnh cho AI
        chat_context = df_processed.to_markdown(index=False)
        
        # 3. Gọi API Gemini (có streaming)
        api_key = st.secrets.get("GEMINI_API_KEY")
        full_response = ""

        if not api_key:
            full_response = "Lỗi: Không tìm thấy Khóa API 'GEMINI_API_KEY'."
            st.sidebar.error(full_response)
        else:
            try:
                client = genai.Client(api_key=api_key)
                
                # Chuyển đổi lịch sử sang định dạng API, loại bỏ prompt mới nhất
                history_for_api = [
                    {"role": m["role"], "parts": [{"text": m["content"]}]}
                    for m in st.session_state.financial_messages[:-1]
                ]
                
                system_instruction = f"""
                Bạn là chuyên gia phân tích tài chính chuyên nghiệp, có khả năng diễn giải dữ liệu.
                Dữ liệu tài chính mà người dùng đã tải và xử lý hiện tại là:
                {chat_context}
                
                Hãy trả lời câu hỏi của người dùng dựa trên dữ liệu này. Tuyệt đối không lặp lại toàn bộ bảng dữ liệu, chỉ tham chiếu các số liệu cụ thể khi cần thiết để hỗ trợ câu trả lời.
                """
                
                # SỬA LỖI: Truyền system_instruction qua config
                config = {"system_instruction": system_instruction}

                # Sử dụng chat session để duy trì bối cảnh (context) cuộc trò chuyện
                chat_session = client.chats.create(
                    model='gemini-2.5-flash', 
                    history=history_for_api,
                    config=config # Đã sửa lỗi: Dùng config thay vì system_instruction trực tiếp
                )
                
                # Gửi tin nhắn mới nhất và stream phản hồi
                with st.sidebar.chat_message("model"):
                    message_placeholder = st.empty()
                    
                    response_stream = chat_session.send_message(prompt, stream=True)
                    
                    for chunk in response_stream:
                        if chunk.text:
                            full_response += chunk.text
                            # Hiệu ứng đánh máy
                            message_placeholder.markdown(full_response + "▌") 
                    
                    # Hoàn tất hiển thị
                    message_placeholder.markdown(full_response)
                
            except APIError as e:
                full_response = f"Lỗi gọi API Gemini: {e}. Vui lòng kiểm tra API Key."
                st.sidebar.error(full_response)
            except Exception as e:
                full_response = f"Lỗi không xác định: {e}"
                st.sidebar.error(full_response)

        # 4. Cập nhật lịch sử session state (lưu phản hồi đầy đủ)
        st.session_state.financial_messages.append({"role": "model", "content": full_response})

else:
    # Hiển thị lịch sử chat khi chưa tải file
    for message in st.session_state.financial_messages:
        with st.sidebar.chat_message(message["role"]):
            st.markdown(message["content"])

    # Vô hiệu hóa input chat
    st.sidebar.chat_input("Vui lòng tải file Excel để bắt đầu trò chuyện...", disabled=True)
    st.info("Vui lòng tải lên file Excel để bắt đầu phân tích.")
