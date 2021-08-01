from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import os


app = FastAPI()

origins = [
    "https://coa-calculator-frontend.herokuapp.com/smithing",
    "https://coa-calculator-frontend.herokuapp.com/crafting",
    "https://coa-calculator-frontend.herokuapp.com/cooking"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

exp_data_file = open(os.path.dirname(__file__) + '/../exp_data.json')
exp_data = json.load(exp_data_file)

artisan_data_file = open(os.path.dirname(__file__) + '/../artisan_data.json')
artisan_data = json.load(artisan_data_file)


@app.get("/exp", tags=["exp"])
async def get_todos() -> dict:
    return exp_data

@app.get("/artisan", tags=["artisan"])
async def get_todos() -> dict:
    return artisan_data