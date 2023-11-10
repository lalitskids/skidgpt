import os
import boto3
import openai
from uuid import uuid4
from json import dumps, loads
from datetime import datetime
from dotenv import load_dotenv
from langchain import PromptTemplate
from langchain.chains import LLMChain
from langchain.schema import Document
from lambda_decorators import cors_headers
from langchain.chat_models import AzureChatOpenAI
load_dotenv()


class LLMService:

    def __init__(self) -> None:

        openai.api_key = os.getenv("OPENAI_API_KEY")
        openai.api_type = os.getenv("OPENAI_API_TYPE")
        openai.api_base = os.getenv("OPENAI_API_BASE")
        openai.api_version = os.getenv("OPENAI_API_VERSION")

        self.chatHistory = []

        # load get summary qna model
        llm = AzureChatOpenAI(deployment_name = os.getenv("DEPLOYMENT_NAME"), openai_api_version = os.getenv("OPENAI_API_VERSION"))
        template = """Act as a Pediatrician, answer the following question {question} using 
            the given context {context} and chat history {chat_history}, True status means nornmal."""
        prompt = PromptTemplate(template=template, input_variables=["context", "question", "chat_history"])
        self.__getQA = LLMChain(llm = llm, prompt = prompt)

        # load model for question suggestions
        llm = AzureChatOpenAI(deployment_name = os.getenv("DEPLOYMENT_NAME"), openai_api_version = os.getenv("OPENAI_API_VERSION"))
        template = """based on the following diagnosis summary: {context}, give me 5 question suggestions."""
        prompt = PromptTemplate(template=template, input_variables=["context"])
        self.__questionSuggestion = LLMChain(llm = llm, prompt = prompt)

    def removeKeys(self, obj):

        if isinstance(obj, dict):
            newObj = {}
            for key, value in obj.items():
                if key == "M":
                    newObj.update(self.removeKeys(value))
                elif key == "L":
                    newObj = self.removeKeys(value)
                elif key in ["S", "BOOL", "NULL", "N"]:
                    newObj = value
                else:
                    newObj[key] = self.removeKeys(value)
            return newObj

        elif isinstance(obj, list):
            return [self.removeKeys(item) for item in obj]

        else:
            return obj

    def getDiagnosiSummaryQA(self, file, userQuery):

        try:

            file["createdAt"] = file["createdAt"].replace(".", ":")
            file["dentalAssessment"]["DMFTIndex"] = str(file["dentalAssessment"]["DMFTIndex"])
            docs = [Document(page_content=dumps(file))]
            print("document created done.......")

            # response = openai.ChatCompletion.create(
            #     model = "gpt-3.5-turbo-0613",
            #     temperature=1,
            #     max_tokens=500,
            #     top_p=1,
            #     frequency_penalty=0,
            #     presence_penalty=0,
            #     messages=[{"role": "user", "content": f"""Act as a Pediatrician, answer the following question {userQuery} using the given context {docs[0].page_content}, True status means nornmal."""}],
            #     stop=None
            # )

            print("model response recieved done.......")
            answer = self.__getQA.run({"context":docs[0].page_content, "question": userQuery, "chat_history": self.chatHistory})
            questions = self.__questionSuggestion.run({"context": docs[0].page_content})

            if len(self.chatHistory) == 4:
                self.chatHistory.pop()

            self.chatHistory.append((userQuery, answer))
            return {"status": 200, "message": "Success", "response": {"answer": answer, "questions": questions}}

        except Exception as e:
            print("some error occur" + str(e))
            return {"status": 400, "message": str(e), "response": ""}


llm = LLMService()

@cors_headers
def handler(event, context):

    print("get summary qa function starts.......")

    body = loads(event.get('body'))

    if body is None:
        return { "statusCode": 400, "response": dumps({ "status": 400, "message": "body is required" }), "headers": {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True,
            } }

    if "screeningId" not in body:
        return { "statusCode": 400, "response": dumps({ "status": 400, "message": "screeningId is required" }), "headers": {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True,
            } }

    if body["screeningId"] == "":
        return { "statusCode": 400, "response": dumps({ "status": 400, "message": "screeningId is required" }), "headers": {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True,
            } }

    if "userQuery" not in body:
        return { "statusCode": 400, "response": dumps({ "status": 400, "message": "userQuery is required" }), "headers": {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True,
            } }

    if body["userQuery"] == "":
        return { "statusCode": 400, "response": dumps({ "status": 400, "message": "userQuery is required" }), "headers": {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True,
            } }

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(os.getenv("SCREENING_TABLE"))
    response = table.get_item(Key = {"id": body["screeningId"]})
    print("got item from db done.......")

    llmResponse = llm.getDiagnosiSummaryQA(response["Item"], body["userQuery"])

    print("add qa to db.......")
    table = dynamodb.Table(os.getenv("QNA_TABLE"))
    table.put_item(Item={
        "id": str(uuid4()).replace("-",""),
        "screeningId": body["screeningId"],
        "userQuery": body["userQuery"],
        "answer": llmResponse["response"],
        "createdAt": str(datetime.now())
    })

    print("returning answer.......")
    return { 'statusCode': llmResponse["status"], 'body': dumps(llmResponse), "headers": {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True,
            } }
