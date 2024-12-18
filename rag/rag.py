from langchain_community.document_loaders.pdf import PyPDFDirectoryLoader # Importing PDF loader from Langchain
from langchain.schema import Document # Importing Document schema from Langchain
from langchain.text_splitter import RecursiveCharacterTextSplitter # Importing text splitter from Langchain
from langchain.vectorstores.chroma import Chroma # Importing Chroma vector store from Langchain
from langchain_community.embeddings import OpenAIEmbeddings # Importing OpenAI embeddings from Langchain
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_ollama import ChatOllama
from dotenv import load_dotenv
import os
import shutil
import json
import pandas as pd

load_dotenv()
openai_api_key = os.getenv('OPEN_AI_API_KEY')

#Dataset loader- This block of code is for checking and testing only. Can be deleted after use.
datasets = os.path.join("data", "inputs", "bpi_datasets")
files = os.listdir(datasets)
print("Files in directory:", files)

if os.path.exists(datasets):
    for file_name in os.listdir(datasets):
        file_path = os.path.join(datasets, file_name)
        
        if file_name.endswith(".parquet"):
            df = pd.read_parquet(file_path)
            print(f"Contents of {file_name}:\n{df}\n") 
else:
    print(f"The path {datasets} does not exist.")
#End of dataset loader test code

def load_pdf_documents(DATA_PATH):
  document_loader = PyPDFDirectoryLoader(DATA_PATH)
  return document_loader.load()
    
def load_json_to_documents(file_path: str) -> list[Document]:
    documents = []
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    for url, content_dict in data.items():
        content = content_dict.get('content', "")
        text_splitter = RecursiveCharacterTextSplitter(
          chunk_size=300,
          chunk_overlap=100,
          length_function=len,
          add_start_index=True,
        )
        chunks = text_splitter.split_text(content)
        for chunk in chunks:
            documents.append(Document(page_content=chunk, metadata={"source": url}))
    
    return documents

def split_text(documents: list[Document]):
  text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=300, 
    chunk_overlap=100, 
    length_function=len,
    add_start_index=True, 
  )

  chunks = text_splitter.split_documents(documents)
  return chunks

def save_to_chroma(chunks: list[Document],CHROMA_PATH):
  if os.path.exists(CHROMA_PATH):
    shutil.rmtree(CHROMA_PATH)

  db = Chroma.from_documents(
    chunks,
    OpenAIEmbeddings(openai_api_key=openai_api_key),
    persist_directory=CHROMA_PATH
  )

  db.persist()
  print(f"Saved {len(chunks)} chunks to {CHROMA_PATH}.")

#Parquet loader
def load_parquet_documents(parquet_folder_path: str) -> list[Document]:
    documents = []
    for file_name in os.listdir(parquet_folder_path):
        if file_name.endswith(".parquet"):
            file_path = os.path.join(parquet_folder_path, file_name)
            # Load parquet file
            df = pd.read_parquet(file_path)
            # Preprocessing
            df = df.dropna()  
            df = df.drop_duplicates()
            
            #Display all contents
            # print(f"Contents of {file_name}:\n{df}\n") 
            
            
            for _, row in df.iterrows():
                # Row to JSON string for consistency
                content = json.dumps(row.to_dict())  
                documents.append(Document(page_content=content, metadata={"source": file_name}))
                
    return documents
  
def generate_data_store(DATA_PATH,CHROMA_PATH,data_type):
  if data_type=='PDF':
    documents = load_pdf_documents(DATA_PATH)
    chunks = split_text(documents)
    save_to_chroma(chunks,CHROMA_PATH)
  elif data_type=='JSON':
    documents = load_json_to_documents(DATA_PATH)
    save_to_chroma(documents,CHROMA_PATH)
  elif data_type == 'PARQUET':
    documents = load_parquet_documents(DATA_PATH)
    save_to_chroma(documents,CHROMA_PATH)
  else:
    print("Invalid data type. Please choose from PDF, JSON, PARQUET.")

def query_rag(query_text,CHROMA_PATH):
  embedding_function = OpenAIEmbeddings(openai_api_key=openai_api_key)
  db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embedding_function)
  results = db.similarity_search_with_relevance_scores(query_text, k=3)
  if len(results) == 0 or results[0][1] < 0.7:
    print(f"Unable to find matching results.")
    return None, None

  context_text = "\n\n - -\n\n".join([doc.page_content for doc, _score in results])
  prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
  prompt = prompt_template.format(context=context_text, question=query_text)
  
  model = ChatOllama(
    model="llama3.2",
    temperature=0,
  )

  messages = [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": prompt}
  ]

  response_text = model.invoke(messages)
 
  sources = [doc.metadata.get("source", None) for doc, _score in results]
 
  formatted_response = response_text.content
  return formatted_response, response_text

# generate_data_store()
# query_text = "What is the purpose of the data operations engineer?"

PROMPT_TEMPLATE = """
Answer the question based only on the following context:
{context}
 - -
Answer the question based on the above context: {question}
"""

# formatted_response, response_text = query_rag(query_text)
# # and finally, inspect our final response!
# print(response_text)

