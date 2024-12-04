import os
from typing import Optional, List

from dotenv import load_dotenv
from fastapi import FastAPI, Body, HTTPException, Query, status
from pydantic import ConfigDict, BaseModel, Field
from pydantic.functional_validators import BeforeValidator

from typing_extensions import Annotated

from bson import ObjectId
import motor.motor_asyncio

load_dotenv()

app = FastAPI(
    title="Student API",
    version="1.0.0", 
    description="Backend Intern Hiring Task"
)
client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGODB_URL"])
db = client.college
student_collection = db.get_collection("students")

# Represents an ObjectId field in the database.
# It will be represented as a `str` on the model so that it can be serialized to JSON.
PyObjectId = Annotated[str, BeforeValidator(str)]

class AddressModel(BaseModel):
    city: str
    country: str


class StudentModel(BaseModel):

    # The primary key for the StudentModel, stored as a `str` on the instance.
    # This will be aliased to `_id` when sent to MongoDB,
    # but provided as `id` in the API requests and responses.
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str = Field(...)
    age: int = Field(...)
    address: AddressModel = Field(...)
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "name": "Jane Doe",
                "age": 22,
                "address": {
                    "city": "Agra",
                    "country": "India"
                } 
            }
        },
    )

class UpdateStudentModel(BaseModel):
    name: Optional[str]
    age: Optional[int]
    address: Optional[AddressModel]

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        schema_extra = {
            "example": {
                "name": "Rahul",
                "age": 20,
                "address": {
                    "city": "Delhi",
                    "country": "India"
                }
            }
        }
    )

class ListResponseStudent(BaseModel):
    name: str
    age: int

class StudentCollection(BaseModel):
    """
    A container holding a list of `StudentModel` instances.

    This exists because providing a top-level array in a JSON response can be a [vulnerability](https://haacked.com/archive/2009/06/25/json-hijacking.aspx/)
    """

    data: List[ListResponseStudent]

class CreateStudentResponse(BaseModel):
    id: str = Field(...)

class GetSingleStudentResponse(BaseModel):
    name: str
    age: int
    address: AddressModel

@app.post(
    "/students/",
    response_description="Add new student",
    response_model=CreateStudentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_student(student: StudentModel = Body(...)):
    """
    Insert a new student record.

    A unique `id` will be created and provided in the response.
    """
    new_student = await student_collection.insert_one(
        student.model_dump(by_alias=True, exclude=["id"])
    )
    created_student = await student_collection.find_one(
        {"_id": new_student.inserted_id}
    )
    return CreateStudentResponse(id=str(created_student["_id"]))


@app.get(
    "/students/",
    response_description="List all students",
    response_model=StudentCollection,
)
async def list_students(
    country: Optional[str] = Query(None, description="Filter by country"),
    age: Optional[int] = Query(None, description="Filter by minimum age")
):
    query = {}
    if country:
        query["address.country"] = country
    if age is not None:
        query["age"] = {"$gte": age}

    students = await student_collection.find(query, {"name": 1, "age": 1, "_id": 0}).to_list(1000)
    return StudentCollection(data=students)


@app.get(
    "/students/{id}",
    response_description="Get a single student",
    response_model=GetSingleStudentResponse
)
async def fetch_student(id: str):
    """
    Get the record for a specific student, looked up by `id`.
    """
    if (
        student := await student_collection.find_one({"_id": ObjectId(id)}, {"_id": 0})
    ) is not None:
        return student
    
    raise HTTPException(status_code=404, detail=f"Student {id} not found")


@app.patch(
    "/students/{id}",
    response_description="Update a student",
    response_model={},
    status_code=status.HTTP_204_NO_CONTENT
)
async def update_student(id: str, student: UpdateStudentModel = Body(...)):
    update_data = {k: v for k, v in student.model_dump(exclude_unset=True).items() if v is not None}
    if len(update_data) > 0:
        update_result = await student_collection.update_one(
            {"_id": ObjectId(id)}, {"$set": update_data}
        )
        if update_result.modified_count == 1:
            return {}

    existing_student = await student_collection.find_one({"_id": ObjectId(id)})
    if existing_student:
        return {}

    raise HTTPException(status_code=404, detail=f"Student {id} not found")


@app.delete(
    "/students/{id}",
    response_description="Delete a student",
    response_model={},
    status_code=status.HTTP_200_OK
)
async def delete_student(id: str):
    delete_result = await student_collection.delete_one({"_id": ObjectId(id)})

    if delete_result.deleted_count == 1:
        return {}

    raise HTTPException(status_code=404, detail=f"Student {id} not found")
