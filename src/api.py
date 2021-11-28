from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import os


app = FastAPI()


origins = [
    "https://coa-calculator.herokuapp.com",
    # "https://coa-calculator.herokuapp.com/smithing",
    # "https://coa-calculator.herokuapp.com/crafting",
    # "https://coa-calculator.herokuapp.com/cooking",
    "http://localhost:3000",
    "localhost:3000"
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

gathering_data_file = open(os.path.dirname(__file__) + '/../gathering_data.json')
gathering_data = json.load(gathering_data_file)

monsters_data_file = open(os.path.dirname(__file__) + '/../monsters_data.json')
monsters_data = json.load(monsters_data_file)

@app.get("/exp", tags=["exp"])
async def get_exp() -> dict:
    return exp_data

@app.get("/artisan", tags=["artisan"])
async def get_artisan() -> dict:
    return artisan_data

@app.get("/gathering", tags=["gathering"])
async def get_gathering() -> dict:
    return gathering_data

@app.get("/monsters", tags=["monsters"])
async def get_monsters() -> dict:
    return monsters_data