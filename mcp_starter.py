import asyncio
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from mcp.server.auth.provider import AccessToken

from upi_service import generate_upi_link
from file_conversion_service import create_upload_link as file_create_upload_link
from image_lens_service import create_upload_link as lens_create_upload_link

# Load environment variables
load_dotenv()
TOKEN = os.getenv("AUTH_TOKEN")
MY_NUMBER = os.getenv("MY_NUMBER")

if TOKEN is None or MY_NUMBER is None:
    raise RuntimeError("Please set AUTH_TOKEN and MY_NUMBER in your .env file.")

from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair

class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str):
        if token == self.token:
            return AccessToken(
                token=token,
                client_id="puch-client",
                scopes=["*"],
                expires_at=None,
            )
        return None

auth = SimpleBearerAuthProvider(TOKEN)
mcp = FastMCP("UPI & FileConvert & Lens MCP Server", auth=auth)

# --- User Session State ---
user_state = {}

MAIN_MENU = (
    "Welcome to the MCP Server! Please select a service by replying with the option number:\n"
    "1. Generate UPI Payment Link\n"
    "2. Convert Text/Doc to PDF or PDF to Text/Doc\n"
    "3. Google Lens Image Search"
)

def reset_user_state(user_id: str):
    user_state[user_id] = {"stage": "menu"}

@mcp.tool
async def validate() -> str:
    return MY_NUMBER

@mcp.tool
async def menu(user_id: str = None) -> str:
    if user_id:
        reset_user_state(user_id)
    return MAIN_MENU

@mcp.tool
async def handle_message(message: str, user_id: str) -> str:
    if user_id not in user_state:
        reset_user_state(user_id)
    return MAIN_MENU

    # Allow plain text trigger here too
    if message and message.strip().lower() == "send me the menu":
        if user_id:
            reset_user_state(user_id)
        return MAIN_MENU

    if state["stage"] == "menu":
        msg = message.strip()
        if msg == "1":
            state["stage"] = "upi_service_ask_app"
            state["upi_apps"] = ["GooglePay", "PhonePe", "Paytm", "BHIM"]
            return (
                "You chose UPI Payment Link Generator.\n"
                "Please select a UPI app by typing its number:\n" +
                "\n".join(f"{i+1}. {app}" for i, app in enumerate(state["upi_apps"]))
            )
        elif msg == "2":
            state["stage"] = "file_conv_ask_direction"
            return (
                "You chose Text/Doc <> PDF Conversion.\n"
                "Please type '1' to convert Text/Doc to PDF or '2' for PDF to Text/Doc."
            )
        elif msg == "3":
            state["stage"] = "lens_ask_generate_link"
            return (
                "You chose Google Lens Image Search.\n"
                "Type '1' to generate a temporary upload link to upload your photo."
            )
        else:
            return "Invalid input. Please select either 1, 2 or 3."

    if state["stage"] == "upi_service_ask_app":
        try:
            choice = int(message.strip())
            if 1 <= choice <= len(state["upi_apps"]):
                state["upi_service"] = state["upi_apps"][choice - 1]
                state["stage"] = "upi_ask_details"
                return (
                    f"You selected {state['upi_service']}.\n"
                    "Please provide payment details in the format:\n"
                    "<recipient_upi_id>;<amount>;<optional_note>\n"
                    "Example: user@upi;100.50;Lunch payment"
                )
            else:
                return "Invalid choice. Please pick a valid number from the list."
        except ValueError:
            return "Please enter a valid number corresponding to a UPI app."

    if state["stage"] == "upi_ask_details":
        parts = message.split(";")
        if len(parts) < 2:
            return "Invalid format. Please provide in <recipient_upi_id>;<amount>;<optional_note> format."
        upi_id = parts[0].strip()
        try:
            amount = float(parts[1].strip())
        except ValueError:
            return "Please enter a valid numeric amount."
        note = parts[2].strip() if len(parts) > 2 else ""
        upi_link = generate_upi_link(service=state["upi_service"], upi_id=upi_id, amount=amount, note=note)
        reset_user_state(user_id)
        return f"UPI Payment Link generated:\n{upi_link}\n\nReturning to main menu:\n{MAIN_MENU}"

    if state["stage"] == "file_conv_ask_direction":
        if message.strip() == "1":
            state["conversion_direction"] = "to_pdf"
            state["stage"] = "file_conv_provide_link"
            upload_link = file_create_upload_link(user_id, direction="to_pdf")
            return (
                f"Please upload your text/doc file here:\n{upload_link}\n"
                "After upload and conversion, you will receive a download link here."
            )
        elif message.strip() == "2":
            state["conversion_direction"] = "to_text"
            state["stage"] = "file_conv_provide_link"
            upload_link = file_create_upload_link(user_id, direction="to_text")
            return (
                f"Please upload your PDF file here:\n{upload_link}\n"
                "After upload and conversion, you will receive a download link here."
            )
        else:
            return "Invalid input. Please type '1' or '2' to specify the conversion direction."

    if state["stage"] == "file_conv_provide_link":
        return "Processing your file. You will get the download link here soon."

    if state["stage"] == "lens_ask_generate_link":
        if message.strip() == "1":
            upload_link = lens_create_upload_link(user_id)
            state["stage"] = "lens_upload_link_generated"
            return (
                f"Here is your temporary upload link:\n{upload_link}\n"
                "Please upload your photo here from your gallery.\n"
                "After upload, Google Lens results will be processed and you will receive them here."
            )
        else:
            return "Invalid input. Please type '1' to generate an upload link."

    if state["stage"] == "lens_upload_link_generated":
        return "Waiting for your photo upload and Google Lens processing. You will receive results here soon."

    reset_user_state(user_id)
    return f"Something went wrong. Returning to main menu.\n{MAIN_MENU}"

@mcp.tool
async def server_message(message: str, user_id: str) -> str:
    if message.strip().lower() == "/mcp message server menu":
        reset_user_state(user_id)
        return MAIN_MENU
    return "Unrecognized server message"

async def main():
    print("🚀 Starting MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    asyncio.run(main())
