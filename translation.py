import streamlit as st
import requests  # 假设调用外部API的库
import os
import json
from dotenv import load_dotenv, find_dotenv
import random
import time
import re
import sqlite3
import datetime
import warnings
 
# 忽略所有的 DeprecationWarning 警告
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

_ = load_dotenv(find_dotenv())    # read local .env file

coze_api_key = os.environ["COZE_API_KEY"]
COZE_BOT_ID = os.environ["COZE_BOT_ID"]
DB_NAME = os.environ["DB_NAME"]

def call_coze_api(query,con_id='123',user_id='zmx', stream=False):
    response_data = send_request(coze_api_key, con_id, COZE_BOT_ID, user_id, query, stream)
    if stream:
        # 流式调用
        return json.loads(response_data[-1])
    else:
        # 非流式调用
        # 填充调用Coze API获得回复的代码，返回为字典
        response = parse_message_object(response_data)
        if response["plugin"] != "":
            ref_info = plugin_text_process(response["plugin"])
            response.update(ref_info)
        return response

def send_request(personal_access_token, con_id, bot_id, user_id, query, stream=False):
    # 填充调用Coze API的具体代码，获得coze的回复，返回为json格式
    url = 'https://api.coze.cn/open_api/v2/chat'
    
    headers = {
        'Authorization': f'Bearer {personal_access_token}',
        'Content-Type': 'application/json',
        'Accept': '*/*',
        'Host': 'api.coze.cn',
        'Connection': 'keep-alive'
    }
    
    data = {
        'conversation_id': con_id,
        'bot_id': bot_id,
        'user': user_id,
        'query': query,
        'stream': stream
    }
    
    if stream:
        # 流式响应
        accumulated_content = ""
        return_messages = []
        # 发送请求并启用流式响应
        with requests.post(url, headers=headers, json=data, stream=True) as response:
            response.raise_for_status()
            
            # 逐行读取数据
            for chunk in response.iter_lines():
                if chunk:
                    decode_chunk = chunk.decode('utf-8')
                    # 去掉"data:"前缀并解析JSON
                    chunk_data = json.loads(decode_chunk.replace("data:", "").strip())
                    # 判断会话是否结束
                    if chunk_data["event"] == "conversation.chat.completed" or chunk_data["event"] == "done":
                        break
                    else:
                        # 判断是否为回答消息
                        if chunk_data["message"]["type"] == "answer":
                            # 累积"content"字段的值
                            accumulated_content += chunk_data["message"]["content"]
                            # 如果"finish"标志为True，输出并清空累积内容
                            if chunk_data["is_finish"]:
                                return_messages.append(accumulated_content)
                                st.chat_message("assistant").write(accumulated_content)
                                accumulated_content = ""
            return return_messages
    else:
        # 非流式响应
        response = requests.post(url, headers=headers, json=data)
        return response.json()

def parse_message_object(message_dict):
    # 解析coze API返回的结果，以字典的形式返回
    # 初始化变量以存储结果
    plugin_data = ""
    last_answer_content = ""

    # 获取messages列表
    messages = message_dict.get('messages', [])

    # 遍历messages列表
    for message in messages:
        # 提取最后一个answer的content值
        if message.get('type') == 'answer':
            last_answer_content = message.get('content', "")

        # 提取plugin数据
        if message.get('type') == 'verbose':
            content_str = message.get('content', "")
            try:
                # 尝试将字符串解析为JSON对象
                content_data = json.loads(content_str)
                # 检查msg_type是否为stream_plugin_finish
                if content_data.get('msg_type') == 'stream_plugin_finish':
                    plugin_data = json.dumps(content_data.get('data'), ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                # 如果解析失败或data不是字典，我们忽略这个条目
                continue

    # 构建结果字典
    result = {
        'plugin': plugin_data.strip(),
        'answer': last_answer_content.strip()
    }
    
    return result

def extract_bracket_content(text):
    # 正则表达式模式，匹配{}及其中的内容，但不包括{}
    pattern = r'({.*?})'
    # 使用findall方法找到所有匹配项
    matches = re.findall(pattern, text)
    return matches

def plugin_text_process(ref_info):
    # 将Plugin输出转化为字典
    # key = ref_web_url，ref_web_name，ref_std，think_process，result
    text = ref_info.replace('\\n', '')
    text = text.replace('\\\\\\\\\\\\\\', '\\')
    text = text.replace('\\\\\\', '')
    text = text[2:-2]
    text = extract_bracket_content(text)[0]
    text=eval(text)
    return text

def get_bot_direct_reply(api_response):
    bot_answer = api_response.get('answer', "")
    bot_answer = json.loads(bot_answer)
    reflection = bot_answer.get('reflection', "")
    intermediate = bot_answer.get('intermediate', "")
    classificationId = bot_answer.get('classificationId', "")
    answer = bot_answer.get('answer', "")
    return answer, reflection, intermediate, classificationId

def clear_messages():
    st.session_state.messages = []

def testcall():
    i = random.random()
    api_response = {'answer': i}
    time.sleep(1)
    return api_response

def db_record(query, answer, reflection,intermediate, classificationId):
    # 将query和answer记录到数据库
    # 连接到数据库，如果数据库不存在，则会创建一个新的数据库
    conn = sqlite3.connect(DB_NAME)
    # 创建一个 cursor 对象，用于执行 SQL 语句
    cursor = conn.cursor()
    # 创建表
    cursor.execute('''CREATE TABLE IF NOT EXISTS datatable
                (date, query, answer, intermediate, reflection, classificationId)''')
    # 插入数据
    # 这里需要将传入的参数转换为元组(tuple)，然后传递给execute方法
    cursor.execute("INSERT INTO datatable VALUES (?, ?, ?, ?, ?, ?)",
                   (datetime.datetime.now(), query, answer, intermediate, 
                    reflection, classificationId))
    # 提交事务
    conn.commit()
    # 关闭连接
    conn.close()


# Streamlit 应用程序界面
def main():
    st.set_page_config(page_title="STE写作助手", page_icon="🦙", layout="centered", initial_sidebar_state="auto", menu_items=None)
    st.title("STE写作助手")
    st.caption("您好，我是一名STE写作助手，我可以为您修改英文文本使其符合ASD-STE100规范，并给出修改建议~")
    # 创建侧边栏
    sidebar = st.sidebar
    # 在左侧列添加组件
    with sidebar:
        # 定义选项列表
        options = ["流式输出", "非流式输出"]
        # 添加单选框
        selected_option = st.radio("选择输出形式：", options)
        # 清空按钮
        st.button("清空", on_click=clear_messages)
    # Initialize the chat messages history
    if "messages" not in st.session_state.keys(): 
        st.session_state.messages = []  
    # 历史对话展示框
    #messages = st.container(height=450)
    # 显示整个对话历史
    for message in st.session_state.messages:
        st.chat_message(message["role"]).write(message["content"], unsafe_allow_html=True)
    if prompt := st.chat_input("Your English text here..."):
        # 将用户输入添加到对话历史中
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        # 设置是否流式显示
        if selected_option == "流式输出":
            stream = True
        else:
            stream = False
        # 调用API获取回复
        with st.spinner('Wait...'):
            api_response = call_coze_api(prompt,'123','zmx', stream) 
            if stream:
                # 流式显示
                answer = api_response.get('answer', "")
                reflection = api_response.get('reflection', "")
                intermediate = api_response.get('intermediate', "")
                classificationId = api_response.get('classificationId', "")
            else:
                # 非流式显示
                answer, reflection, intermediate, classificationId = get_bot_direct_reply(api_response)
            # 完整结果的输出
            if classificationId is None:
                classificationId = ""
            classificationId = "写作类型："+ str(classificationId)
            st.session_state.messages.append({"role": "assistant", "content": classificationId})
            st.chat_message("assistant").write(classificationId)
            if intermediate is None:
                intermediate = ""
            intermediate = "反思初稿："+intermediate
            st.session_state.messages.append({"role": "assistant", "content": intermediate})
            st.chat_message("assistant").write(intermediate)
            if answer is None:
                answer = ""
            answer = "二次修改："+answer
            # 将LLM的回答添加到对话历史中
            st.session_state.messages.append({"role": "assistant", "content": answer})
            st.chat_message("assistant").write(answer)
            if reflection != []:
                # 使用列表推导式将列表中的每个元素转换为字符串，并用换行符连接
                reflection = '<br>'.join(str(item) for item in reflection)
                reflection = "反思改进：<br>"+reflection
                st.session_state.messages.append({"role": "assistant", "content": reflection})
                st.chat_message("assistant").write(reflection, unsafe_allow_html=True)
            else:
                reflection = ""
            # 调用函数，记录对话历史到数据库
            db_record(prompt, answer, reflection,intermediate, classificationId)


if __name__ == '__main__':
    # 命令行启动 streamlit run translation.py
    # 持续运行 nohup streamlit run translation.py --server.port 8504 >translation.log &
    # 监控输出 tail -f translation.log
    # 关闭 kill [$PID]
    # 进程查看 ps -ef | grep translation
    try:
        main()
    except Exception as e:
        st.error(f"An error occurred: {e}")
        print(f"An error occurred: {e}")
