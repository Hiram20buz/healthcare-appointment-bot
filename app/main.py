from fastapi import FastAPI, HTTPException
from typing import List
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
import os
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import datetime
from pydantic import BaseModel, Field
from typing import Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY= os.getenv("OPENAI_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
PASSWORD = os.getenv("PASSWORD")

pool = psycopg2.pool.SimpleConnectionPool(2, 3, dsn=DATABASE_URL)

print("Connection pool created successfully using DATABASE_URL")


def send_confirmation_email(recipient_email, name, date, time, reason):
    # Configuration (Use environment variables for secrets!)
    sender_email = SENDER_EMAIL
    password = PASSWORD

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = "Appointment Confirmation - Health Clinic"

    body = f"""
    <html>
        <body>
            <h2>Hello, {name}!</h2>
            <p>Your appointment has been successfully scheduled.</p>
            <hr>
            <p><strong>Date:</strong> {date}</p>
            <p><strong>Time:</strong> {time}</p>
            <p><strong>Reason:</strong> {reason}</p>
            <hr>
            <p>If you need to reschedule, please contact us 24 hours in advance.</p>
        </body>
    </html>
    """
    message.attach(MIMEText(body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, recipient_email, message.as_string())


@tool
def get_current_date_time() -> str:
    """
    Returns the current date and time in a human-readable format
    and an ISO format for database queries.
    """
    now = datetime.datetime.now()

    # Formatted Date: Friday, February 20, 2026
    readable_date = now.strftime("%A, %B %d, %Y")

    # Formatted Time: 01:32 PM
    readable_time = now.strftime("%I:%M %p")

    # ISO Format: 2026-02-20
    iso_date = now.date().isoformat()

    return (
        f"Today is {readable_date}. "
        f"The current time is {readable_time}. "
        f"Query format: {iso_date}"
    )


@tool
def list_available_services():
    """
    List all available medical services, including their modality,
    price, and duration in minutes.
    """
    conn = None
    try:
        # 1. Get connection from pool
        conn = pool.getconn()

        # 2. Use context managers for the transaction and cursor
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, name, price, duration_minutes, modality 
                    FROM services 
                    WHERE is_active = TRUE 
                    ORDER BY name ASC;
                """
                )
                rows = cur.fetchall()

        if not rows:
            return "No hay servicios disponibles actualmente."

        # 3. Format the output
        lines = [
            f"- {s['id']} {s['name']} ({s['modality']}): ${s['price']}, {s['duration_minutes']} min"
            for s in rows
        ]
        return "\n".join(lines)

    except Exception as e:
        # In a real tool, you might want to log this instead of just printing
        print(f"❌ Database Error: {e}")
        return "Lo siento, hubo un error al consultar el catálogo de servicios."

    finally:
        # 4. Crucial: Always return the connection to the pool
        if conn:
            pool.putconn(conn)


@tool
def check_availability(date: str) -> str:
    """
    Checks the availability of appointments for a specific date (YYYY-MM-DD).
    Returns a list of occupied times or a confirmation that the day is free.
    """
    query = """
        SELECT appointment_time 
        FROM appointments 
        WHERE appointment_date = %s 
        AND status != 'Cancelled' 
        ORDER BY appointment_time ASC;
    """

    conn = None
    try:
        # For psycopg2, we use .getconn() instead of .acquire()
        conn = pool.getconn()

        with conn.cursor() as cur:
            # Use %s for psycopg2 placeholders (instead of $1)
            cur.execute(query, (date,))
            rows = cur.fetchall()

            if not rows:
                return f"Everything is available for {date}."

            # rows is a list of tuples, e.g., [(datetime.time(10, 0),), (datetime.time(11, 30),)]
            occupied = ", ".join([r[0].strftime("%H:%M") for r in rows])

            return f"On {date}, these slots are occupied: {occupied}."

    except Exception as e:
        print(f"Database error: {e}")
        return "Error checking availability."

    finally:
        # ALWAYS put the connection back in the pool
        if conn is not None:
            pool.putconn(conn)


class BookingArgs(BaseModel):
    full_name: str = Field(description="Patient's full name")
    phone: str = Field(description="Patient's phone number")
    email: Optional[str] = Field(None, description="Patient's email address")
    birth_date: str = Field(description="Birth date in YYYY-MM-DD format")
    age: int = Field(description="Patient's age")
    gender: str = Field(description="Patient's gender")
    service_id: int = Field(description="ID of the service being booked")
    appointment_date: str = Field(description="Date of appointment YYYY-MM-DD")
    appointment_time: str = Field(description="Time of appointment HH:MM")
    reason: Optional[str] = Field(None, description="Reason for the visit")


@tool(args_schema=BookingArgs)
def book_appointment(
    full_name,
    phone,
    email,
    birth_date,
    age,
    gender,
    service_id,
    appointment_date,
    appointment_time,
    reason,
) -> str:
    """
    Registers a patient (if new) and books an appointment.
    Checks for conflicts before finalizing.
    """
    conn = None
    try:
        conn = pool.getconn()
        # Set autocommit to False to handle the transaction manually
        conn.autocommit = False
        with conn.cursor() as cur:

            # 1. Upsert Patient
            cur.execute(
                """
                INSERT INTO patients (full_name, phone, email, birth_date, age, gender) 
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (phone) DO UPDATE SET full_name = EXCLUDED.full_name 
                RETURNING id;
            """,
                (full_name, phone, email, birth_date, age, gender),
            )
            patient_id = cur.fetchone()[0]

            # 2. Check availability (Double-check to prevent race conditions)
            cur.execute(
                """
                SELECT id FROM appointments 
                WHERE appointment_date=%s AND appointment_time=%s AND status!='Cancelled'
            """,
                (appointment_date, appointment_time),
            )

            if cur.fetchone():
                conn.rollback()
                return "This slot is already occupied."

            # 3. Insert Appointment
            cur.execute(
                """
                INSERT INTO appointments (patient_id, service_id, appointment_date, appointment_time, status, reason)
                VALUES (%s, %s, %s, %s, 'Pending', %s) RETURNING id;
            """,
                (patient_id, service_id, appointment_date, appointment_time, reason),
            )
            appointment_id = cur.fetchone()[0]

            # 4. Commit the transaction
            conn.commit()
            try:
                send_confirmation_email(
                    email, full_name, appointment_date, appointment_time, reason
                )
                email_status = "Confirmation email sent."
            except Exception as e:
                print(f"Email failed: {e}")

            return f"Appointment successfully scheduled! ID: {appointment_id}."

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error booking: {e}")
        return "Internal error during booking."

    finally:
        if conn:
            pool.putconn(conn)


llm = ChatOpenAI(model="gpt-4o-mini")

agent = create_react_agent(
    model=llm,
    tools=[
        list_available_services,
        get_current_date_time,
        check_availability,
        book_appointment,
    ],
    prompt="You are a helpful assistant",
)
###

app = FastAPI()


class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # Prepare inputs for the agent
        inputs = {"messages": [HumanMessage(content=request.message)]}

        # Run the agent
        result = agent.invoke(inputs)

        # Extract the content of the last message
        final_message = result["messages"][-1].content

        return {"response": final_message}

    except Exception as e:
        # Note: Fixed the typo 'status_status' to 'status_code'
        raise HTTPException(status_code=500, detail=str(e))