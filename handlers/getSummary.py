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

        # load get summary model
        llm = AzureChatOpenAI(deployment_name = os.getenv("DEPLOYMENT_NAME"), openai_api_version = os.getenv("OPENAI_API_VERSION"))
        template = """provide diagnosis summary of the key information based on the following 
            report: {context} within 500 words. In the response, pragraph for overall summary with patient general information,
            pragaraph for what is normal, pragaraph for what is abnormal."""
        prompt = PromptTemplate(template=template, input_variables=["context"])
        self.__getSummary = LLMChain(llm = llm, prompt = prompt)

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

    def getDiagnosiSummary(self, file):

        try:

            file["createdAt"] = file["createdAt"].replace(".", ":")
            file["dentalAssessment"]["DMFTIndex"] = str(file["dentalAssessment"]["DMFTIndex"])
            docs = [Document(page_content=dumps(file))]
            print("document created done.......")

            answer = f"Dear {file.get('firstName', 'Patient')},\n\n"
            answer += f"I hope this letter finds you well. I am writing to provide you with the results of {file.get('firstName', 'Patient')} recent physical examination which took place on the {file.get('createdAt', '')} under the supervision of SKIDS. \n\n"
            print("answer first stage done.......")

            # response = openai.ChatCompletion.create(
            #     model = "gpt-3.5-turbo-0613",
            #     temperature=1,
            #     max_tokens=500,
            #     top_p=1,
            #     frequency_penalty=0,
            #     presence_penalty=0,
            #     messages=[{"role": "user", "content": f"""provide diagnosis summary of the key information based on the following 
            #         report: {docs[0].page_content} within 500 words. In the response, pragraph for overall summary with patient general information,
            #         pragaraph for what is normal, pragaraph for what is abnormal."""}],
            #     stop=None
            # )

            answer += self.__getSummary.run({"context": docs[0].page_content})
            print("model response recieved done.......")

            answer += "\n\nWishing you good health and wellness,\n\n"
            answer += f"{file.get('firstName', 'Patient')}/{file.get('doctor', 'Doctor')}"

            questions = self.__questionSuggestion.run({"context": answer})

            print("answer second stage done.......")
            return {"status": 200, "message": "Success", "response": {"summary": answer, "questions": questions}}

        except Exception as e:
            print("some error occur" + str(e))
            return {"status": 400, "message": str(e), "response": {}}


llm = LLMService()

@cors_headers
def handler(event, context):

    print("get summary function starts.......")

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

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(os.getenv("SCREENING_TABLE"))
    response = table.get_item(Key = {"id": body["screeningId"]})
    print("got item from db done.......")

    llmResponse = llm.getDiagnosiSummary(response["Item"])

    print("add summary to db.......")
    table = dynamodb.Table(os.getenv("SUMMARY_TABLE"))
    table.put_item(Item={
        "id": str(uuid4()).replace("-",""),
        "screeningId": body["screeningId"],
        "summary": llmResponse["response"],
        "createdAt": str(datetime.now())
    })

    print("returning answer.......")
    return { 'statusCode': llmResponse["status"], 'body': dumps(llmResponse), "headers": {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True,
            }}
