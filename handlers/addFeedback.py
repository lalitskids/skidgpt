import os
import boto3
from uuid import uuid4
from json import loads, dumps
from datetime import datetime
from dotenv import load_dotenv
from lambda_decorators import cors_headers
load_dotenv()

@cors_headers
def handler(event, context):

    try:

        print("get add feedback function starts.......")

        body = loads(event.get('body'))

        if body is None:
            return { "statusCode": 400, "response": dumps({ "status": 400, "message": "body is required" }), "headers": {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True,
            } }

        summaryId = ""
        qnaId = ""
        feedback = 0

        if "summaryId" in body:
            if body["summaryId"] != "":
                summaryId = body["summaryId"]

        if "qnaId" in body:
            if body["qnaId"] != "":
                qnaId = body["qnaId"]

        if "feedback" in body:
            feedback = body["feedback"]

        print("got item from db done.......")
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(os.getenv("FEEDBACK_TABLE"))
        table.put_item(Item={
            "id": str(uuid4()).replace("-",""),
            "summaryId": summaryId,
            "qnaId": qnaId,
            "feedback": feedback,
            "createdAt": str(datetime.now())
        })

        print("returning answer.......")
        return { 'statusCode': 200, 'body': dumps({ "status": 200, "message": "feedback added succesfully" }), "headers": {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True,
            } }

    except Exception as e:
        return { 'statusCode': 400, 'body': dumps({ "status": 400, "message": str(e) }), "headers": {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True,
            } }
