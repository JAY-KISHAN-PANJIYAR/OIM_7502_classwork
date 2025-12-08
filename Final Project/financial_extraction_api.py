#!/usr/bin/env python3
"""
FastAPI Financial Data Extraction Service
Extracts financial statements from bank PDFs using Gemini API
"""

import json
import logging
import os
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from logging.handlers import RotatingFileHandler

import requests
import urllib3
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from pydantic import BaseModel
from supabase import Client, create_client
from typing import Any, Dict, List, Optional


# Disable SSL warnings when SSL verification is bypassed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables
load_dotenv()

# Configure logging for production
def setup_logging():
    """Setup comprehensive logging for production use"""

    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Configure root logger with UTF-8 encoding for Windows compatibility
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        handlers=[
            # Console handler with UTF-8 encoding for emojis
            logging.StreamHandler(sys.stdout),
            # File handler with rotation for persistent logs with UTF-8 encoding
            RotatingFileHandler(
                os.path.join(log_dir, 'financial_extraction.log'),
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'  # Add UTF-8 encoding
            )
        ]
    )

    # Set console handler to use UTF-8
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            # For Windows, configure stdout to handle UTF-8
            if sys.platform == 'win32':
                import codecs
                handler.stream = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

    # Create specific logger for our app
    logger = logging.getLogger("financial_extraction_api")
    logger.setLevel(logging.INFO)

    return logger

# Initialize logger
logger = setup_logging()

# Initialize FastAPI
app = FastAPI(
    title="Bank Financial Data Extraction API",
    description="Extract financial statements from bank reports using AI",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Fiscal Year Conversion Map (English to Nepali)
FISCAL_YEAR_CONVERSION = {
    "2000/01": "2057/58", "2001/02": "2058/59", "2002/03": "2059/60",
    "2003/04": "2060/61", "2004/05": "2061/62", "2005/06": "2062/63",
    "2006/07": "2063/64", "2007/08": "2064/65", "2008/09": "2065/66",
    "2009/10": "2066/67", "2010/11": "2067/68", "2011/12": "2068/69",
    "2012/13": "2069/70", "2013/14": "2070/71", "2014/15": "2071/72",
    "2015/16": "2072/73", "2016/17": "2073/74", "2017/18": "2074/75",
    "2018/19": "2075/76", "2019/20": "2076/77", "2020/21": "2077/78",
    "2021/22": "2078/79", "2022/23": "2079/80", "2023/24": "2080/81",
    "2024/25": "2081/82", "2025/26": "2082/83"
}

def convert_fiscal_year_to_nepali(fiscal_year: str) -> str:
    """
    Convert English fiscal year (AD) to Nepali fiscal year (BS) if it's less than 2030
    Examples: 2019/20 -> 2076/77, 2078/79 -> 2078/79 (already Nepali)
    """
    if not fiscal_year or '/' not in fiscal_year:
        return fiscal_year

    try:
        year_start = int(fiscal_year.split('/')[0])
        if year_start >= 2030:
            # Already in Nepali format, BS
            return fiscal_year
        else:
            # Convert from English (AD) to Nepali (BS)
            converted = FISCAL_YEAR_CONVERSION.get(fiscal_year, fiscal_year)
            if converted != fiscal_year:
                logger.info(f"🔄 Converted fiscal year: {fiscal_year} (AD) -> {converted} (BS)")
            return converted
    except (ValueError, IndexError):
        logger.warning(f"⚠️ Could not parse fiscal year: {fiscal_year}")
        return fiscal_year

# Function to extract filename from PDF URL
def get_filename_from_url(pdf_url: str) -> str:
    """Extract filename from PDF URL, with fallback to timestamp if needed"""
    try:
        # Try to get filename from URL
        from urllib.parse import urlparse
        parsed = urlparse(pdf_url)
        path = parsed.path
        filename = path.split('/')[-1]

        # If filename has extension and seems valid
        if filename.lower().endswith('.pdf') and len(filename) > 4:
            return filename

        # Fallback: Use URL path parts and timestamp
        path_parts = [p for p in path.split('/') if p]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if path_parts:
            # Use last 2 path parts + timestamp
            clean_parts = [p.replace(' ', '_') for p in path_parts[-2:]]
            return f"{'_'.join(clean_parts)}_{timestamp}.pdf"

        # Last resort: Generic name with timestamp
        return f"document_{timestamp}.pdf"

    except Exception as e:
        logger.warning(f"Error extracting filename from URL: {e}, using fallback")
        return f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

# Pydantic models
class FinancialDataRequest(BaseModel):
    bank_symbol: str  # Changed from bank_name to bank_symbol for efficiency
    fiscal_year: str  # e.g., "2080/81"
    report_type: str  # "annual" or "quarterly"
    quarter: Optional[str] = None  # "Q1", "Q2", "Q3", "Q4" if quarterly

    def __init__(self, **data):
        # Normalize quarter before validation
        if data.get('quarter') is not None:
            quarter_value = str(data['quarter']).strip()
            if quarter_value == "" or quarter_value.lower() in ["null", "none"]:
                data['quarter'] = None
            elif len(quarter_value) > 5:
                data['quarter'] = quarter_value[:5]  # Truncate to 5 chars
            else:
                data['quarter'] = quarter_value
        super().__init__(**data)

class AddDocumentRequest(BaseModel):
    bank_symbol: str  # e.g., "ADBL", "HBL"
    fiscal_year: str  # e.g., "2078/79", "2021/22"
    report_type: str  # "annual" or "quarterly"
    quarter: Optional[str] = None  # "Q1", "Q2", "Q3", "Q4" (required if quarterly)
    pdf_url: str  # Direct PDF URL
    added_by: Optional[str] = None  # Name of person who added this document
    method: Optional[str] = "manual"  # "manual", "api", "static", "dynamic"

    def __init__(self, **data):
        # Normalize quarter before validation
        if data.get('quarter') is not None:
            quarter_value = str(data['quarter']).strip()
            if quarter_value == "" or quarter_value.lower() in ["null", "none"]:
                data['quarter'] = None
            elif len(quarter_value) > 5:
                data['quarter'] = quarter_value[:5]  # Truncate to 5 chars
            else:
                data['quarter'] = quarter_value

        # Normalize method
        if data.get('method') is None or data.get('method').strip() == "":
            data['method'] = "manual"

        super().__init__(**data)

class FinancialDataResponse(BaseModel):
    bank_symbol: str
    bank_name: str
    fiscal_year: str
    quarter: Optional[str]
    document_type: str
    income_statement: Optional[Dict[str, Any]]
    balance_sheet: Optional[Dict[str, Any]]
    cashflow_statement: Optional[Dict[str, Any]]
    key_ratios: Optional[Dict[str, Any]]
    data_source: str  # "database" or "extracted"
    extraction_confidence: Optional[str]
    extracted_at: Optional[str]

@app.get("/")
async def root():
    return {
        "message": "Bank Financial Data Extraction API",
        "version": "1.0.0",
        "endpoints": {
            "GET /banks": "List all available banks",
            "POST /extract": "Extract financial data (Legacy method)",
            "POST /extract-bytes": "Extract financial data (New PDF bytes method - 80% faster)",
            "POST /add-document": "Add new document for extraction",
            "GET /financial-data/{bank_symbol}": "Get all data for a bank"
        },
        "recommended_endpoint": "/extract-bytes - Faster and more reliable"
    }

@app.get("/banks")
async def get_banks():
    """Get list of all available banks"""
    try:
        result = supabase.table("banks").select("symbol, bank_name, website").execute()
        return {"banks": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching banks: {str(e)}")

def get_bank_info_by_symbol(bank_symbol: str):
    """Get bank information by symbol"""
    try:
        result = supabase.table("banks").select("*").eq("symbol", bank_symbol).execute()
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error getting bank info: {e}")
        return None

def get_bank_info(bank_name: str):
    """Get bank information by name (legacy function)"""
    try:
        result = supabase.table("banks").select("*").ilike("bank_name", f"%{bank_name}%").execute()
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error getting bank info: {e}")
        return None

def check_existing_data(bank_id: int, fiscal_year: str, quarter: Optional[str] = None):
    """Check if financial data already exists in database"""
    try:
        logger.info(f"🔍 Checking for existing data: bank_id={bank_id}, fiscal_year={fiscal_year}, quarter={quarter}")

        # Create a list of fiscal years to search for (both Nepali and English equivalents)
        fiscal_years_to_check = [fiscal_year]

        # Find English equivalent if we have a Nepali year
        try:
            year_start = int(fiscal_year.split('/')[0])
            if year_start >= 2030:
                # This is Nepali format, find English equivalent
                for eng_year, nep_year in FISCAL_YEAR_CONVERSION.items():
                    if nep_year == fiscal_year:
                        fiscal_years_to_check.append(eng_year)
                        logger.info(f"🔍 Also checking English fiscal year equivalent: {eng_year}")
                        break
        except (ValueError, IndexError):
            pass

        # Get ALL records for this bank and any matching fiscal year
        all_records = []
        for fy in fiscal_years_to_check:
            result = supabase.table("financial_statements").select("*").eq("bank_id", bank_id).eq("fiscal_year", fy).execute()
            if result.data:
                logger.info(f"📊 Found {len(result.data)} records for bank_id={bank_id}, fiscal_year={fy}")
                all_records.extend(result.data)

        logger.info(f"📊 Found {len(all_records)} total records across all fiscal year formats")

        # Manual filtering for quarter
        matching_records = []
        for record in all_records:
            record_quarter = record.get("quarter")

            if quarter:
                # Looking for specific quarter
                if record_quarter == quarter:
                    matching_records.append(record)
            else:
                # Looking for annual report (null, empty, or None quarter)
                if not record_quarter or record_quarter == "" or record_quarter is None:
                    matching_records.append(record)

        logger.info(f"📊 Found {len(matching_records)} records matching quarter criteria")

        if matching_records:
            existing_record = matching_records[0]
            logger.info(f"✅ Found existing record - ID: {existing_record.get('id')}")

            # Check if record has meaningful financial data
            income_stmt = existing_record.get("income_statement")
            balance_sheet = existing_record.get("balance_sheet")
            cashflow_stmt = existing_record.get("cashflow_statement")

            # More thorough data checking
            has_income = income_stmt and income_stmt not in [None, {}, "null", ""] and len(str(income_stmt)) > 10
            has_balance = balance_sheet and balance_sheet not in [None, {}, "null", ""] and len(str(balance_sheet)) > 10
            has_cashflow = cashflow_stmt and cashflow_stmt not in [None, {}, "null", ""] and len(str(cashflow_stmt)) > 10

            logger.info(f"📋 Data availability check:")
            logger.info(f"   Income Statement: {has_income}")
            logger.info(f"   Balance Sheet: {has_balance}")
            logger.info(f"   Cashflow Statement: {has_cashflow}")

            if has_income or has_balance or has_cashflow:
                logger.info(f"✅ FOUND EXISTING DATA - SKIPPING EXTRACTION!")
                return existing_record
            else:
                logger.warning(f"⚠️ Record exists but no meaningful financial data found")
                return None

        logger.info(f"❌ No existing data found for the specified criteria")
        return None

    except Exception as e:
        logger.error(f"❌ Error checking existing data: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_document_for_extraction(bank_id: int, fiscal_year: str, report_type: str, quarter: Optional[str] = None):
    """Find document in financial_documents table for extraction"""
    try:
        # Get bank symbol for direct matching
        bank_result = supabase.table("banks").select("symbol").eq("id", bank_id).execute()
        bank_symbol = bank_result.data[0]["symbol"] if bank_result.data else None

        logger.info(f"Looking for document: bank_id={bank_id}, bank_symbol={bank_symbol}, fiscal_year={fiscal_year}, report_type={report_type}, quarter={quarter}")

        # Create a list of fiscal years to search for (both Nepali and English equivalents)
        fiscal_years_to_check = [fiscal_year]

        # Find English equivalent if we have a Nepali year
        try:
            year_start = int(fiscal_year.split('/')[0])
            if year_start >= 2030:
                # This is Nepali format, find English equivalent
                for eng_year, nep_year in FISCAL_YEAR_CONVERSION.items():
                    if nep_year == fiscal_year:
                        fiscal_years_to_check.append(eng_year)
                        logger.info(f"🔍 Also checking English fiscal year equivalent: {eng_year}")
                        break
            else:
                # This is English format, find Nepali equivalent
                nep_year = FISCAL_YEAR_CONVERSION.get(fiscal_year)
                if nep_year:
                    fiscal_years_to_check.append(nep_year)
                    logger.info(f"🔍 Also checking Nepali fiscal year equivalent: {nep_year}")
        except (ValueError, IndexError):
            pass

        logger.info(f"🔍 Searching for fiscal years: {fiscal_years_to_check}")

        # Try to find documents with any of the fiscal year formats in financial_documents table
        for fy in fiscal_years_to_check:
            # Build query for financial_documents
            query = supabase.table("financial_documents").select("*").eq("bank_id", bank_id).eq("fiscal_year", fy).eq("report_type", report_type)

            # Add quarter filter if needed
            if quarter and report_type.lower() == "quarterly":
                query = query.eq("quarter", quarter)
            elif report_type.lower() == "annual":
                query = query.is_("quarter", "null")

            result = query.execute()
            if result.data and len(result.data) > 0:
                logger.info(f"✅ Found matching document in financial_documents: {result.data[0]['id']}")
                return result.data[0]

        logger.info(f"❌ No document found in financial_documents for fiscal years: {fiscal_years_to_check}")
        return None

    except Exception as e:
        logger.error(f"Error getting document: {e}")
        import traceback
        traceback.print_exc()
        return None

async def extract_financial_data_from_pdf(pdf_url: str, bank_symbol: str, fiscal_year: str):
    """Extract financial data from PDF using Gemini API"""
    temp_file = None
    uploaded_file = None
    temp_file_path = None

    try:
        logger.info(f"Starting extraction for {bank_symbol} from {pdf_url}")

        # Download PDF with comprehensive error handling and SSL bypass
        logger.info("Downloading PDF...")

        # Headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/pdf,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        # Session with retries and SSL bypass
        session = requests.Session()
        session.headers.update(headers)

        # Configure session for SSL bypass and retries
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Try multiple download strategies
        download_success = False
        response = None

        strategies = [
            {"verify": True, "timeout": 60, "stream": True},  # Standard approach
            {"verify": False, "timeout": 60, "stream": True},  # SSL bypass
            {"verify": False, "timeout": 120, "stream": False},  # SSL bypass + no streaming
        ]

        for i, strategy in enumerate(strategies, 1):
            try:
                logger.info(f"Attempting download strategy {i}/{len(strategies)}: {strategy}")
                response = session.get(pdf_url, **strategy)
                response.raise_for_status()

                # Verify we got a PDF
                content_type = response.headers.get('content-type', '').lower()
                if 'pdf' in content_type or len(response.content) > 1000:  # Basic PDF validation
                    download_success = True
                    logger.info(f"✅ Download successful with strategy {i}")
                    break
                else:
                    logger.warning(f"⚠️ Strategy {i} returned non-PDF content: {content_type}")

            except requests.exceptions.SSLError as e:
                logger.error(f"❌ SSL error with strategy {i}: {e}")
                continue
            except requests.exceptions.Timeout as e:
                logger.error(f"❌ Timeout error with strategy {i}: {e}")
                continue
            except requests.exceptions.ConnectionError as e:
                logger.error(f"❌ Connection error with strategy {i}: {e}")
                continue
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Request error with strategy {i}: {e}")
                continue

        if not download_success or not response:
            raise Exception(f"Failed to download PDF after trying {len(strategies)} strategies")

        logger.info(f"PDF downloaded successfully, size: {len(response.content)} bytes, content-type: {response.headers.get('content-type', 'unknown')}")

        # Validate PDF content
        if len(response.content) < 1000:
            raise Exception(f"Downloaded file too small ({len(response.content)} bytes), likely not a valid PDF")

        # Check for PDF magic header
        if not response.content.startswith(b'%PDF'):
            logger.warning("⚠️ Warning: Downloaded content doesn't start with PDF header, proceeding anyway...")

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name
        logger.info(f"PDF saved to temporary file: {temp_file_path}")

        # Upload to Gemini
        logger.info("Uploading to Gemini...")
        uploaded_file = genai.upload_file(path=temp_file_path, display_name=f"Bank Report {bank_symbol}")
        logger.info(f"File uploaded to Gemini: {uploaded_file.name}")

        # Extract year from fiscal_year for JSON structure
        year_for_json = fiscal_year.split('/')[1] if '/' in fiscal_year else fiscal_year

        # Enhanced prompt with detailed JSON schema for Nepali banks
        prompt = f"""
        Extract financial data from this {bank_symbol} bank document. Return ONLY a valid JSON object with the following structure (no additional text, explanations, or markdown).

        IMPORTANT: If the document contains both Bank and Group/Consolidated data, extract ONLY the Bank data (standalone bank without subsidiaries).

        {{
            "income_statement": {{
                "stock_id": null,
                "year": {year_for_json},
                "interest_income": null,
                "interest_expense": null,
                "net_interest_income": null,
                "fee_and_commission_income": null,
                "fee_and_commission_expense": null,
                "net_fee_and_commission_income": null,
                "net_interest_fee_and_commission_income": null,
                "net_trading_income": null,
                "other_operating_income": null,
                "total_operating_income": null,
                "impairment_charge_reversal": null,
                "net_operating_income": null,
                "operating_expense": null,
                "personnel_expenses": null,
                "other_operating_expenses": null,
                "depreciation_amortisation": null,
                "operating_profit": null,
                "non_operating_income": null,
                "non_operating_expense": null,
                "profit_before_income_tax": null,
                "income_tax_expense": null,
                "current_tax": null,
                "deferred_tax": null,
                "profit_for_period": null,
                "profit_attributable_to": null,
                "equity_holders_of_bank": null,
                "non_controlling_interest": null,
                "earnings_per_share": null,
                "earnings_per_share_basic": null,
                "earnings_per_share_diluted": null
            }},
            "balance_sheet": {{
                "stock_id": null,
                "year": {year_for_json},
                "assets": null,
                "cash_and_cash_equivalent": null,
                "due_from_nepal_rastra_bank": null,
                "placement_with_bank_and_financial_institutions": null,
                "derivative_financial_instruments": null,
                "other_trading_assets": null,
                "loan_and_advances_to_b_flst": null,
                "loans_and_advances_to_customers": null,
                "investment_securities": null,
                "current_tax_assets": null,
                "investment_in_subsidiaries": null,
                "investment_in_associates": null,
                "investment_property": null,
                "property_and_equipment": null,
                "goodwill_and_intangible_assets": null,
                "deferred_tax_assets": null,
                "other_assets": null,
                "total_assets": null,
                "liabilities": null,
                "due_to_bank_and_financial_institutions": null,
                "due_to_nepal_rastra_bank": null,
                "derivative_financial_instruments2": null,
                "deposits_from_customers": null,
                "borrowings": null,
                "current_tax_liabilities": null,
                "provisions": null,
                "deferred_tax_liabilities": null,
                "other_liabilities": null,
                "debt_securities_issued": null,
                "subordinated_liabilities": null,
                "total_liabilities": null,
                "equity": null,
                "share_capital": null,
                "share_premium": null,
                "retained_earnings": null,
                "reserves": null,
                "total_equity_attributable_to_equity_holders": null,
                "non_controlling_interest": null,
                "total_equity": null,
                "total_liabilities_and_equity": null,
                "contingent_liabilities_and_commitment": null,
                "net_assets_value_per_share": null
            }},
            "cashflow_statement": {{
                "stock_id": null,
                "year": {year_for_json},
                "cash_flows_from_operating_activities": null,
                "interest_received": null,
                "fees_and_other_income_received": null,
                "dividends_received": null,
                "receipt_from_other_operating_activities": null,
                "interest_paid": null,
                "commission_and_fees_paid": null,
                "cash_payment_to_employees": null,
                "other_expense_paid": null,
                "operating_cash_flows_before_changes_in_assets_and_liabilities": null,
                "changes_in_operating_assets": null,
                "due_from_nepal_rastra_bank": null,
                "placement_with_bank_and_financial_institutions": null,
                "other_trading_assets": null,
                "loan_and_advances_to_bank_and_financial_institutions": null,
                "loans_and_advances_to_customers": null,
                "other_assets": null,
                "changes_in_operating_liabilities": null,
                "due_to_bank_and_financial_institutions": null,
                "due_to_nepal_rastra_bank": null,
                "deposits_from_customers": null,
                "borrowings": null,
                "other_liabilities": null,
                "net_cash_from_operating_activities_before_tax": null,
                "income_taxes_paid": null,
                "net_cash_from_operating_activities": null,
                "cash_flows_from_investing_activities": null,
                "purchase_of_investment_securities": null,
                "receipt_from_sales_of_investment_securities": null,
                "purchase_of_property_and_equipment": null,
                "receips_from_sales_of_property_and_equipment": null,
                "purchase_of_intangible_assets": null,
                "receipt_from_sales_of_intangible_assets": null,
                "purchase_of_investment_property": null,
                "receipt_from_sales_of_investment_property": null,
                "interest_received2": null,
                "dividends_received2": null,
                "net_cash_used_in_investing_activities": null,
                "cash_flows_from_financing_activities": null,
                "receipt_from_issue_of_debt_securities": null,
                "repayment_of_debt_securities": null,
                "receipt_from_issue_of_subordinated_liabilities": null,
                "repayment_of_subordinated_liabilities": null,
                "receipt_from_issue_of_shares": null,
                "dividends_paid": null,
                "interest_paid_financing": null,
                "other_receipt_or_payment": null,
                "net_cash_from_financing_activities": null,
                "net_change_in_cash_equivalents": null,
                "cash_and_cash_equivalents_at_1_shrawan": null,
                "effect_of_exchange_rate_fluctuations": null,
                "cash_and_cash_equivalents_at_ashadh_end": null
            }}
        }}

        Instructions:
        1. Extract numerical values in NPR (without commas or currency symbols)
        2. For fiscal year {fiscal_year}, extract data from the Bank column only (not Group/Consolidated)
        3. If a field is not found or not applicable, keep it as null
        4. Convert all amounts to actual numbers (e.g., "1,234,567" becomes 1234567)
        5. Make sure year field uses the ending year (e.g., for 2078/79, use 2079)
        """

        # Generate content
        logger.info("Generating content with Gemini...")
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content([prompt, uploaded_file])
        logger.info(f"Gemini response received, length: {len(response.text) if response.text else 0}")

        # Parse JSON response
        try:
            # Clean the response text
            json_text = response.text.strip()
            logger.debug(f"Raw response: {json_text[:200]}...")  # Show first 200 chars

            if json_text.startswith("```json"):
                json_text = json_text[7:]
            if json_text.endswith("```"):
                json_text = json_text[:-3]

            financial_data = json.loads(json_text)
            logger.info("JSON parsing successful")
            return financial_data, "high"

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.debug(f"Response text: {response.text}")
            return None, "low"

    except Exception as e:
        logger.error(f"Error extracting financial data: {e}")
        import traceback
        traceback.print_exc()
        return None, "low"

    finally:
        # Cleanup
        if uploaded_file:
            try:
                logger.info(f"Cleaning up Gemini file: {uploaded_file.name}")
                genai.delete_file(uploaded_file.name)
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up Gemini file: {cleanup_error}")

        if temp_file_path and os.path.exists(temp_file_path):
            try:
                logger.info(f"Cleaning up temporary file: {temp_file_path}")
                os.unlink(temp_file_path)
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up temp file: {cleanup_error}")

@app.post("/extract", response_model=FinancialDataResponse)
async def extract_financial_data(request: FinancialDataRequest):
    """Extract financial data for specified bank and period"""

    try:
        # Normalize quarter field - ensure it's None or valid format and not too long
        if request.quarter:
            request.quarter = request.quarter.strip()
            if request.quarter == "" or request.quarter.lower() == "null" or request.quarter.lower() == "none":
                request.quarter = None
            elif len(request.quarter) > 5:
                # Truncate or normalize to standard format
                request.quarter = request.quarter[:5]
                logger.warning(f"⚠️ Quarter value truncated to 5 chars: {request.quarter}")

        # Convert fiscal year to Nepali format if needed
        original_fiscal_year = request.fiscal_year
        request.fiscal_year = convert_fiscal_year_to_nepali(request.fiscal_year)

        if original_fiscal_year != request.fiscal_year:
            logger.info(f"📅 User provided fiscal year in AD format: {original_fiscal_year}, using BS format: {request.fiscal_year}")

        # Get bank information by symbol (more efficient)
        bank_info = get_bank_info_by_symbol(request.bank_symbol)
        if not bank_info:
            raise HTTPException(status_code=404, detail=f"Bank '{request.bank_symbol}' not found")

        bank_id = bank_info["id"]
        bank_symbol = bank_info["symbol"]

        # Check if data already exists
        existing_data = check_existing_data(bank_id, request.fiscal_year, request.quarter)

        if existing_data:
            # Return existing data
            return FinancialDataResponse(
                bank_symbol=bank_symbol,
                bank_name=bank_info["bank_name"],
                fiscal_year=request.fiscal_year,
                quarter=request.quarter,
                document_type=existing_data["document_type"],
                income_statement=existing_data["income_statement"],
                balance_sheet=existing_data["balance_sheet"],
                cashflow_statement=existing_data["cashflow_statement"],
                key_ratios=existing_data["key_ratios"],
                data_source="database",
                extraction_confidence=existing_data["extraction_confidence"],
                extracted_at=existing_data["extracted_at"]
            )

        # Find document for extraction
        document = get_document_for_extraction(bank_id, request.fiscal_year, request.report_type, request.quarter)

        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"No document found for {request.bank_symbol} {request.fiscal_year} {request.report_type}{' ' + request.quarter if request.quarter else ''}. Use /add-document endpoint to add the document first."
            )

        # Extract financial data
        financial_data, confidence = await extract_financial_data_from_pdf(document["pdf_url"], bank_symbol, request.fiscal_year)

        if not financial_data:
            raise HTTPException(status_code=500, detail="Failed to extract financial data from document")

        # Derive document_type from report_type and quarter
        document_type = f"{request.report_type}_report" if request.report_type == "annual" else f"quarterly_report_{request.quarter}" if request.quarter else "quarterly_report"

        # Store in database (no financial_document_id needed - we have all info already)
        financial_record = {
            "bank_id": bank_id,
            "bank_symbol": bank_symbol,
            "bank_name": bank_info["bank_name"],
            "pdf_url": document["pdf_url"],
            "filename": get_filename_from_url(document["pdf_url"]),
            "document_type": document_type,
            "fiscal_year": request.fiscal_year,
            "quarter": request.quarter,
            "report_period": f"{request.fiscal_year} {request.report_type.title()}{' ' + request.quarter if request.quarter else ''}",
            "income_statement": financial_data.get("income_statement"),
            "balance_sheet": financial_data.get("balance_sheet"),
            "cashflow_statement": financial_data.get("cashflow_statement"),
            "key_ratios": financial_data.get("key_ratios"),
            "extraction_confidence": confidence,
            "extraction_method": "gemini_api",
            "api_model_used": "gemini-2.5-flash",
            "extracted_by": "api_service"
        }

        # Insert into database
        result = supabase.table("financial_statements").insert(financial_record).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to save extracted data")

        return FinancialDataResponse(
            bank_symbol=bank_symbol,
            bank_name=bank_info["bank_name"],
            fiscal_year=request.fiscal_year,
            quarter=request.quarter,
            document_type=document_type,  # Use the derived document_type
            income_statement=financial_data.get("income_statement"),
            balance_sheet=financial_data.get("balance_sheet"),
            cashflow_statement=financial_data.get("cashflow_statement"),
            key_ratios=financial_data.get("key_ratios"),
            data_source="extracted",
            extraction_confidence=confidence,
            extracted_at=datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Internal server error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

async def extract_financial_data_from_pdf_bytes(pdf_url: str, bank_symbol: str, fiscal_year: str):
    """Extract financial data from PDF using Gemini API with PDF bytes approach (New Method)"""

    try:
        logger.info(f"🚀 Starting PDF bytes extraction for {bank_symbol} from {pdf_url}")

        # Download PDF with comprehensive error handling and SSL bypass
        logger.info("📥 Downloading PDF...")

        # Headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/pdf,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        # Session with retries and SSL bypass
        session = requests.Session()
        session.headers.update(headers)

        # Configure session for SSL bypass and retries
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Try multiple download strategies
        download_success = False
        response = None

        strategies = [
            {"verify": True, "timeout": 60, "stream": True},  # Standard approach
            {"verify": False, "timeout": 60, "stream": True},  # SSL bypass
            {"verify": False, "timeout": 120, "stream": False},  # SSL bypass + no streaming
        ]

        for i, strategy in enumerate(strategies, 1):
            try:
                logger.info(f"Attempting download strategy {i}/{len(strategies)}: {strategy}")
                response = session.get(pdf_url, **strategy)
                response.raise_for_status()

                # Verify we got a PDF
                content_type = response.headers.get('content-type', '').lower()
                if 'pdf' in content_type or len(response.content) > 1000:  # Basic PDF validation
                    download_success = True
                    logger.info(f"✅ Download successful with strategy {i}")
                    break
                else:
                    logger.warning(f"⚠️ Strategy {i} returned non-PDF content: {content_type}")

            except requests.exceptions.SSLError as e:
                logger.error(f"❌ SSL error with strategy {i}: {e}")
                continue
            except requests.exceptions.Timeout as e:
                logger.error(f"❌ Timeout error with strategy {i}: {e}")
                continue
            except requests.exceptions.ConnectionError as e:
                logger.error(f"❌ Connection error with strategy {i}: {e}")
                continue
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Request error with strategy {i}: {e}")
                continue

        if not download_success or not response:
            raise Exception(f"Failed to download PDF after trying {len(strategies)} strategies")

        pdf_bytes = response.content
        logger.info(f"📄 PDF downloaded successfully, size: {len(pdf_bytes)} bytes, content-type: {response.headers.get('content-type', 'unknown')}")

        # Validate PDF content
        if len(pdf_bytes) < 1000:
            raise Exception(f"Downloaded file too small ({len(pdf_bytes)} bytes), likely not a valid PDF")

        # Check for PDF magic header
        if not pdf_bytes.startswith(b'%PDF'):
            logger.warning("⚠️ Warning: Downloaded content doesn't start with PDF header, proceeding anyway...")

        # Create PDF blob for Gemini (NEW APPROACH - No file upload needed!)
        logger.info("🔧 Creating PDF blob for Gemini...")
        pdf_blob = {
            "mime_type": "application/pdf",
            "data": pdf_bytes
        }

        # Extract year from fiscal_year for JSON structure
        year_for_json = fiscal_year.split('/')[1] if '/' in fiscal_year else fiscal_year

        # Enhanced prompt with detailed JSON schema for Nepali banks
        prompt = [
            pdf_blob,
            f"""Extract financial data from this {bank_symbol} bank document. Return ONLY a valid JSON object with the following structure (no additional text, explanations, or markdown).

        IMPORTANT: If the document contains both Bank and Group/Consolidated data, extract ONLY the Bank data (standalone bank without subsidiaries).

        {{
            "income_statement": {{
                "stock_id": null,
                "year": {year_for_json},
                "interest_income": null,
                "interest_expense": null,
                "net_interest_income": null,
                "fee_and_commission_income": null,
                "fee_and_commission_expense": null,
                "net_fee_and_commission_income": null,
                "net_interest_fee_and_commission_income": null,
                "net_trading_income": null,
                "other_operating_income": null,
                "total_operating_income": null,
                "impairment_charge_reversal": null,
                "net_operating_income": null,
                "operating_expense": null,
                "personnel_expenses": null,
                "other_operating_expenses": null,
                "depreciation_amortisation": null,
                "operating_profit": null,
                "non_operating_income": null,
                "non_operating_expense": null,
                "profit_before_income_tax": null,
                "income_tax_expense": null,
                "current_tax": null,
                "deferred_tax": null,
                "profit_for_period": null,
                "profit_attributable_to": null,
                "equity_holders_of_bank": null,
                "non_controlling_interest": null,
                "earnings_per_share": null,
                "earnings_per_share_basic": null,
                "earnings_per_share_diluted": null
            }},
            "balance_sheet": {{
                "stock_id": null,
                "year": {year_for_json},
                "assets": null,
                "cash_and_cash_equivalent": null,
                "due_from_nepal_rastra_bank": null,
                "placement_with_bank_and_financial_institutions": null,
                "derivative_financial_instruments": null,
                "other_trading_assets": null,
                "loan_and_advances_to_b_flst": null,
                "loans_and_advances_to_customers": null,
                "investment_securities": null,
                "current_tax_assets": null,
                "investment_in_subsidiaries": null,
                "investment_in_associates": null,
                "investment_property": null,
                "property_and_equipment": null,
                "goodwill_and_intangible_assets": null,
                "deferred_tax_assets": null,
                "other_assets": null,
                "total_assets": null,
                "liabilities": null,
                "due_to_bank_and_financial_institutions": null,
                "due_to_nepal_rastra_bank": null,
                "derivative_financial_instruments2": null,
                "deposits_from_customers": null,
                "borrowings": null,
                "current_tax_liabilities": null,
                "provisions": null,
                "deferred_tax_liabilities": null,
                "other_liabilities": null,
                "debt_securities_issued": null,
                "subordinated_liabilities": null,
                "total_liabilities": null,
                "equity": null,
                "share_capital": null,
                "share_premium": null,
                "retained_earnings": null,
                "reserves": null,
                "total_equity_attributable_to_equity_holders": null,
                "non_controlling_interest": null,
                "total_equity": null,
                "total_liabilities_and_equity": null,
                "contingent_liabilities_and_commitment": null,
                "net_assets_value_per_share": null
            }},
            "cashflow_statement": {{
                "stock_id": null,
                "year": {year_for_json},
                "cash_flows_from_operating_activities": null,
                "interest_received": null,
                "fees_and_other_income_received": null,
                "dividends_received": null,
                "receipt_from_other_operating_activities": null,
                "interest_paid": null,
                "commission_and_fees_paid": null,
                "cash_payment_to_employees": null,
                "other_expense_paid": null,
                "operating_cash_flows_before_changes_in_assets_and_liabilities": null,
                "changes_in_operating_assets": null,
                "due_from_nepal_rastra_bank": null,
                "placement_with_bank_and_financial_institutions": null,
                "other_trading_assets": null,
                "loan_and_advances_to_bank_and_financial_institutions": null,
                "loans_and_advances_to_customers": null,
                "other_assets": null,
                "changes_in_operating_liabilities": null,
                "due_to_bank_and_financial_institutions": null,
                "due_to_nepal_rastra_bank": null,
                "deposits_from_customers": null,
                "borrowings": null,
                "other_liabilities": null,
                "net_cash_from_operating_activities_before_tax": null,
                "income_taxes_paid": null,
                "net_cash_from_operating_activities": null,
                "cash_flows_from_investing_activities": null,
                "purchase_of_investment_securities": null,
                "receipt_from_sales_of_investment_securities": null,
                "purchase_of_property_and_equipment": null,
                "receips_from_sales_of_property_and_equipment": null,
                "purchase_of_intangible_assets": null,
                "receipt_from_sales_of_intangible_assets": null,
                "purchase_of_investment_property": null,
                "receipt_from_sales_of_investment_property": null,
                "interest_received2": null,
                "dividends_received2": null,
                "net_cash_used_in_investing_activities": null,
                "cash_flows_from_financing_activities": null,
                "receipt_from_issue_of_debt_securities": null,
                "repayment_of_debt_securities": null,
                "receipt_from_issue_of_subordinated_liabilities": null,
                "repayment_of_subordinated_liabilities": null,
                "receipt_from_issue_of_shares": null,
                "dividends_paid": null,
                "interest_paid_financing": null,
                "other_receipt_or_payment": null,
                "net_cash_from_financing_activities": null,
                "net_change_in_cash_equivalents": null,
                "cash_and_cash_equivalents_at_1_shrawan": null,
                "effect_of_exchange_rate_fluctuations": null,
                "cash_and_cash_equivalents_at_ashadh_end": null
            }}
        }}

        Instructions:
        1. Extract numerical values in NPR (without commas or currency symbols)
        2. For fiscal year {fiscal_year}, extract data from the Bank column only (not Group/Consolidated)
        3. If a field is not found or not applicable, keep it as null
        4. Convert all amounts to actual numbers (e.g., "1,234,567" becomes 1234567)
        5. Make sure year field uses the ending year (e.g., for 2078/79, use 2079)
        """
        ]

        # Generate content using PDF bytes (NO FILE UPLOAD NEEDED!)
        logger.info("🤖 Generating content with Gemini using PDF bytes...")
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        logger.info(f"✅ Gemini response received, length: {len(response.text) if response.text else 0}")

        # Parse JSON response
        try:
            # Clean the response text
            json_text = response.text.strip()
            logger.debug(f"📋 Raw response: {json_text[:200]}...")  # Show first 200 chars

            if json_text.startswith("```json"):
                json_text = json_text[7:]
            if json_text.endswith("```"):
                json_text = json_text[:-3]

            financial_data = json.loads(json_text)
            logger.info("✅ JSON parsing successful")
            return financial_data, "high"

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parsing error: {e}")
            logger.debug(f"Response text: {response.text}")
            return None, "low"

    except Exception as e:
        logger.error(f"❌ Error extracting financial data with PDF bytes method: {e}")
        import traceback
        traceback.print_exc()
        return None, "low"

    # NO CLEANUP NEEDED! No temporary files or uploaded files to clean up


@app.post("/extract-bytes", response_model=FinancialDataResponse)
async def extract_financial_data_bytes(request: FinancialDataRequest):
    """Extract financial data using PDF bytes method (New & Faster) - 80% faster than /extract"""

    try:
        # Normalize quarter field - ensure it's None or valid format and not too long
        if request.quarter:
            request.quarter = request.quarter.strip()
            if request.quarter == "" or request.quarter.lower() == "null" or request.quarter.lower() == "none":
                request.quarter = None
            elif len(request.quarter) > 5:
                # Truncate or normalize to standard format
                request.quarter = request.quarter[:5]
                logger.warning(f"⚠️ Quarter value truncated to 5 chars: {request.quarter}")

        # Convert fiscal year to Nepali format if needed
        original_fiscal_year = request.fiscal_year
        request.fiscal_year = convert_fiscal_year_to_nepali(request.fiscal_year)

        if original_fiscal_year != request.fiscal_year:
            logger.info(f"📅 User provided fiscal year in AD format: {original_fiscal_year}, using BS format: {request.fiscal_year}")

        logger.info(f"🚀 PDF Bytes extraction requested for {request.bank_symbol} {request.fiscal_year} {request.quarter or 'Annual'}")

        # Get bank information by symbol (more efficient)
        bank_info = get_bank_info_by_symbol(request.bank_symbol)
        if not bank_info:
            raise HTTPException(status_code=404, detail=f"Bank '{request.bank_symbol}' not found")

        bank_id = bank_info["id"]
        bank_symbol = bank_info["symbol"]

        # Check if data already exists (same logic as original)
        existing_data = check_existing_data(bank_id, request.fiscal_year, request.quarter)

        if existing_data:
            logger.info("✅ Found existing data in database - returning from cache")
            # Return existing data
            return FinancialDataResponse(
                bank_symbol=bank_symbol,
                bank_name=bank_info["bank_name"],
                fiscal_year=request.fiscal_year,
                quarter=request.quarter,
                document_type=existing_data["document_type"],
                income_statement=existing_data["income_statement"],
                balance_sheet=existing_data["balance_sheet"],
                cashflow_statement=existing_data["cashflow_statement"],
                key_ratios=existing_data["key_ratios"],
                data_source="database",
                extraction_confidence=existing_data["extraction_confidence"],
                extracted_at=existing_data["extracted_at"]
            )

        # Find document for extraction (same logic as original)
        document = get_document_for_extraction(bank_id, request.fiscal_year, request.report_type, request.quarter)

        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"No document found for {request.bank_symbol} {request.fiscal_year} {request.report_type}{' ' + request.quarter if request.quarter else ''}. Use /add-document endpoint to add the document first."
            )

        # Extract financial data using PDF bytes method
        financial_data, confidence = await extract_financial_data_from_pdf_bytes(document["pdf_url"], bank_symbol, request.fiscal_year)

        if not financial_data:
            raise HTTPException(status_code=500, detail="Failed to extract financial data from document using PDF bytes method")

        # Derive document_type from report_type and quarter
        document_type = f"{request.report_type}_report" if request.report_type == "annual" else f"quarterly_report_{request.quarter}" if request.quarter else "quarterly_report"

        # Store in database (no financial_document_id needed - we have all info already)
        financial_record = {
            "bank_id": bank_id,
            "bank_symbol": bank_symbol,
            "bank_name": bank_info["bank_name"],
            "pdf_url": document["pdf_url"],
            "filename": get_filename_from_url(document["pdf_url"]),
            "document_type": document_type,
            "fiscal_year": request.fiscal_year,
            "quarter": request.quarter,
            "report_period": f"{request.fiscal_year} {request.report_type.title()}{' ' + request.quarter if request.quarter else ''}",
            "income_statement": financial_data.get("income_statement"),
            "balance_sheet": financial_data.get("balance_sheet"),
            "cashflow_statement": financial_data.get("cashflow_statement"),
            "key_ratios": financial_data.get("key_ratios"),
            "extraction_confidence": confidence,
            "extraction_method": "gemini_api_bytes",  # Mark as bytes method
            "api_model_used": "gemini-2.5-flash",
            "extracted_by": "api_service_bytes"
        }

        # Insert into database
        result = supabase.table("financial_statements").insert(financial_record).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to save extracted data")

        logger.info("✅ PDF bytes extraction completed successfully")

        return FinancialDataResponse(
            bank_symbol=bank_symbol,
            bank_name=bank_info["bank_name"],
            fiscal_year=request.fiscal_year,
            quarter=request.quarter,
            document_type=document_type,  # Use the derived document_type
            income_statement=financial_data.get("income_statement"),
            balance_sheet=financial_data.get("balance_sheet"),
            cashflow_statement=financial_data.get("cashflow_statement"),
            key_ratios=financial_data.get("key_ratios"),
            data_source="extracted_bytes",
            extraction_confidence=confidence,
            extracted_at=datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ PDF bytes extraction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error in PDF bytes method: {str(e)}")


@app.post("/add-document")
async def add_document(request: AddDocumentRequest):
    """
    Add a new document directly to financial_documents table

    This allows manual entry of documents that weren't automatically scraped.
    You can specify who added the document via the 'added_by' field.
    """

    try:
        # Get bank information by symbol
        bank_info = get_bank_info_by_symbol(request.bank_symbol)
        if not bank_info:
            raise HTTPException(status_code=404, detail=f"Bank '{request.bank_symbol}' not found")

        # Validate report_type
        if request.report_type.lower() not in ["annual", "quarterly"]:
            raise HTTPException(status_code=400, detail="report_type must be 'annual' or 'quarterly'")

        # Validate quarter for quarterly reports
        if request.report_type.lower() == "quarterly" and not request.quarter:
            raise HTTPException(status_code=400, detail="quarter is required for quarterly reports (Q1, Q2, Q3, or Q4)")

        # Normalize fiscal year
        fiscal_year = request.fiscal_year.strip()

        # Determine who added this
        added_by = request.added_by if request.added_by else "manual_entry"

        # Add document to financial_documents table
        financial_doc = {
            "bank_id": bank_info["id"],
            "bank_symbol": request.bank_symbol.upper(),
            "pdf_url": request.pdf_url,
            "fiscal_year": fiscal_year,
            "report_type": request.report_type.lower(),
            "quarter": request.quarter.upper() if request.quarter else None,
            "method": request.method,
            "added_by": added_by
        }

        doc_result = supabase.table("financial_documents").insert(financial_doc).execute()

        if not doc_result.data:
            raise HTTPException(status_code=500, detail="Failed to add document")

        return {
            "message": "Document added successfully to financial_documents",
            "document_id": doc_result.data[0]["id"],
            "bank_symbol": request.bank_symbol,
            "fiscal_year": fiscal_year,
            "report_type": request.report_type.lower(),
            "quarter": request.quarter,
            "pdf_url": request.pdf_url,
            "method": request.method,
            "added_by": added_by
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding document: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error adding document: {str(e)}")

@app.get("/financial-data/{bank_symbol}")
async def get_bank_financial_data(bank_symbol: str):
    """Get all financial data for a specific bank"""

    try:
        result = supabase.table("financial_statements").select("*").eq("bank_symbol", bank_symbol).order("fiscal_year", desc=True).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail=f"No financial data found for bank {bank_symbol}")

        return {
            "bank_symbol": bank_symbol,
            "total_reports": len(result.data),
            "financial_data": result.data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching financial data: {str(e)}")

@app.get("/financial-stats/{bank_symbol}")
async def get_bank_statistics(bank_symbol: str):
    """
    Get comprehensive statistics about available financial reports for a bank

    Returns:
    - Total report counts (annual vs quarterly)
    - Data completeness metrics
    - Fiscal year breakdown with available/missing quarters
    """

    try:
        logger.info(f"📊 Fetching statistics for {bank_symbol}")

        # Get bank information
        bank_info = supabase.table("banks").select("*").eq("symbol", bank_symbol.upper()).execute()

        if not bank_info.data:
            raise HTTPException(status_code=404, detail=f"Bank '{bank_symbol}' not found")

        bank_id = bank_info.data[0]['id']
        bank_name = bank_info.data[0]['bank_name']

        # Get all financial statements for this bank
        result = supabase.table("financial_statements").select("*").eq("bank_id", bank_id).execute()

        if not result.data:
            return {
                "bank_symbol": bank_symbol,
                "bank_name": bank_name,
                "summary": {
                    "total_reports": 0,
                    "annual_reports_count": 0,
                    "quarterly_reports_count": 0,
                    "fiscal_years_covered": 0
                },
                "message": "No financial data available for this bank"
            }

        records = result.data
        total_reports = len(records)

        logger.info(f"📈 Found {total_reports} records for {bank_symbol}")

        # Initialize statistics containers
        annual_reports = []
        quarterly_reports = []
        by_fiscal_year = defaultdict(lambda: {
            'annual': [],
            'quarterly': [],
            'quarters': set()
        })

        # Data completeness statistics
        complete_income = 0
        complete_balance = 0
        complete_cashflow = 0
        all_three_complete = 0

        # Process each record
        for record in records:
            fiscal_year = record.get('fiscal_year')
            quarter = record.get('quarter')

            # Normalize fiscal year to Nepali format for consistent grouping
            normalized_fiscal_year = fiscal_year
            if fiscal_year:
                try:
                    year_start = int(fiscal_year.split('/')[0])
                    if year_start < 2030:
                        # This is English format, convert to Nepali
                        nepali_equivalent = FISCAL_YEAR_CONVERSION.get(fiscal_year)
                        if nepali_equivalent:
                            normalized_fiscal_year = nepali_equivalent
                            logger.debug(f"Converted fiscal year {fiscal_year} → {nepali_equivalent}")
                except (ValueError, IndexError):
                    pass

            # Check data completeness
            has_income = record.get('income_statement') and len(str(record.get('income_statement'))) > 50
            has_balance = record.get('balance_sheet') and len(str(record.get('balance_sheet'))) > 50
            has_cashflow = record.get('cashflow_statement') and len(str(record.get('cashflow_statement'))) > 50

            if has_income:
                complete_income += 1
            if has_balance:
                complete_balance += 1
            if has_cashflow:
                complete_cashflow += 1
            if has_income and has_balance and has_cashflow:
                all_three_complete += 1

            # Categorize by report type (use normalized fiscal year)
            if quarter and quarter.strip() and quarter.lower() != 'null':
                # Quarterly report
                quarterly_reports.append(record)
                by_fiscal_year[normalized_fiscal_year]['quarterly'].append(record)
                by_fiscal_year[normalized_fiscal_year]['quarters'].add(quarter)
            else:
                # Annual report
                annual_reports.append(record)
                by_fiscal_year[normalized_fiscal_year]['annual'].append(record)

            # Store original fiscal year format for reference
            by_fiscal_year[normalized_fiscal_year].setdefault('original_formats', set()).add(fiscal_year)

        # Analyze by fiscal year
        fiscal_years_sorted = sorted(by_fiscal_year.keys(), reverse=True)
        year_statistics = []

        for year in fiscal_years_sorted:
            year_data = by_fiscal_year[year]
            annual_count = len(year_data['annual'])
            quarterly_count = len(year_data['quarterly'])
            available_quarters = sorted(year_data['quarters'])

            # Get original formats found in database
            original_formats = list(year_data.get('original_formats', {year}))

            # Determine missing quarters
            expected_quarters = {'Q1', 'Q2', 'Q3', 'Q4'}
            missing_quarters = sorted(expected_quarters - year_data['quarters'])

            year_statistics.append({
                'fiscal_year': year,
                'original_formats': original_formats,  # Show what formats are actually in DB
                'annual_count': annual_count,
                'quarterly_count': quarterly_count,
                'available_quarters': available_quarters,
                'missing_quarters': missing_quarters,
                'is_complete': len(missing_quarters) == 0 and annual_count > 0
            })

        # Prepare comprehensive statistics response
        statistics = {
            "bank_symbol": bank_symbol,
            "bank_name": bank_name,
            "bank_id": bank_id,
            "summary": {
                "total_reports": total_reports,
                "annual_reports_count": len(annual_reports),
                "quarterly_reports_count": len(quarterly_reports),
                "fiscal_years_covered": len(by_fiscal_year)
            },
            "data_completeness": {
                "income_statement_count": complete_income,
                "balance_sheet_count": complete_balance,
                "cashflow_statement_count": complete_cashflow,
                "all_statements_complete": all_three_complete,
                "completeness_percentage": round(all_three_complete/total_reports*100, 2) if total_reports > 0 else 0
            },
            "by_fiscal_year": year_statistics,
            "latest_data": {
                "latest_fiscal_year": fiscal_years_sorted[0] if fiscal_years_sorted else None,
                "has_latest_annual": len(by_fiscal_year[fiscal_years_sorted[0]]['annual']) > 0 if fiscal_years_sorted else False,
                "latest_quarters": sorted(by_fiscal_year[fiscal_years_sorted[0]]['quarters']) if fiscal_years_sorted else []
            }
        }

        logger.info(f"✅ Statistics generated successfully for {bank_symbol}")
        return statistics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating statistics: {str(e)}")

@app.get("/document-stats/{bank_symbol}")
async def get_document_statistics(bank_symbol: str):
    """
    Get comprehensive statistics about available documents in financial_documents table for a bank

    Returns:
    - Total documents available for extraction
    - Document types breakdown (annual, quarterly)
    - Fiscal year coverage with document counts
    - Quarter availability
    """

    try:
        logger.info(f"📄 Fetching document statistics for {bank_symbol}")

        # Get bank info
        bank_info = get_bank_info_by_symbol(bank_symbol)
        if not bank_info:
            raise HTTPException(status_code=404, detail=f"Bank '{bank_symbol}' not found")

        bank_id = bank_info['id']
        bank_name = bank_info['bank_name']

        logger.info(f"Found bank: {bank_name} (ID: {bank_id})")

        # Fetch all documents for this bank from financial_documents table
        logger.info(f"🔍 Fetching documents from financial_documents table for bank_id={bank_id}")
        docs_result = supabase.table("financial_documents").select("*").eq("bank_id", bank_id).execute()

        if not docs_result.data:
            return {
                "bank_symbol": bank_symbol,
                "bank_name": bank_name,
                "summary": {
                    "total_documents": 0,
                    "annual_reports": 0,
                    "quarterly_reports": 0,
                    "fiscal_years_covered": 0
                },
                "message": "No documents found in financial_documents for this bank"
            }

        records = docs_result.data
        total_documents = len(records)
        logger.info(f"📈 Found {total_documents} documents for {bank_symbol}")

        # Initialize statistics containers
        by_report_type = defaultdict(list)
        by_fiscal_year = defaultdict(lambda: {
            'documents': [],
            'annual_count': 0,
            'quarterly_count': 0,
            'quarters': set(),
            'original_formats': set()
        })

        annual_reports = 0
        quarterly_reports = 0

        # Process each record
        for record in records:
            report_type = record.get('report_type', 'unknown')
            fiscal_year = record.get('fiscal_year')
            quarter = record.get('quarter')

            # Normalize fiscal year to Nepali format for consistent grouping
            normalized_fiscal_year = fiscal_year
            if fiscal_year:
                try:
                    year_start = int(fiscal_year.split('/')[0])
                    if year_start < 2030:
                        # This is English format, convert to Nepali
                        nepali_equivalent = FISCAL_YEAR_CONVERSION.get(fiscal_year)
                        if nepali_equivalent:
                            normalized_fiscal_year = nepali_equivalent
                            logger.debug(f"Converted fiscal year {fiscal_year} → {nepali_equivalent}")
                except (ValueError, IndexError):
                    pass

            # Count by report type
            if report_type == 'annual':
                annual_reports += 1
            elif report_type == 'quarterly':
                quarterly_reports += 1

            # Group by report type
            by_report_type[report_type].append(record)

            # Group by fiscal year
            if fiscal_year:
                by_fiscal_year[normalized_fiscal_year]['documents'].append(record)
                by_fiscal_year[normalized_fiscal_year]['original_formats'].add(fiscal_year)

                if report_type == 'annual':
                    by_fiscal_year[normalized_fiscal_year]['annual_count'] += 1
                elif report_type == 'quarterly':
                    by_fiscal_year[normalized_fiscal_year]['quarterly_count'] += 1
                    if quarter:
                        by_fiscal_year[normalized_fiscal_year]['quarters'].add(quarter)

        # Analyze by fiscal year
        fiscal_years_sorted = sorted(by_fiscal_year.keys(), reverse=True)
        year_statistics = []

        for year in fiscal_years_sorted:
            year_data = by_fiscal_year[year]
            doc_count = len(year_data['documents'])
            available_quarters = sorted(year_data['quarters'])

            # Get original formats found in database
            original_formats = list(year_data['original_formats'])

            # Determine missing quarters
            expected_quarters = {'Q1', 'Q2', 'Q3', 'Q4'}
            missing_quarters = sorted(expected_quarters - year_data['quarters'])

            year_statistics.append({
                'fiscal_year': year,
                'original_formats': original_formats,
                'total_documents': doc_count,
                'annual_reports': year_data['annual_count'],
                'quarterly_reports': year_data['quarterly_count'],
                'available_quarters': available_quarters,
                'missing_quarters': missing_quarters,
                'has_annual': year_data['annual_count'] > 0,
                'has_all_quarters': len(missing_quarters) == 0
            })

        # Prepare comprehensive statistics response
        statistics = {
            "bank_symbol": bank_symbol,
            "bank_name": bank_name,
            "bank_id": bank_id,
            "summary": {
                "total_documents": total_documents,
                "annual_reports": annual_reports,
                "quarterly_reports": quarterly_reports,
                "fiscal_years_covered": len(by_fiscal_year)
            },
            "by_report_type": {
                report_type: len(docs) for report_type, docs in sorted(by_report_type.items(), key=lambda x: len(x[1]), reverse=True)
            },
            "by_fiscal_year": year_statistics,
            "latest_data": {
                "latest_fiscal_year": fiscal_years_sorted[0] if fiscal_years_sorted else None,
                "latest_year_document_count": len(by_fiscal_year[fiscal_years_sorted[0]]['documents']) if fiscal_years_sorted else 0,
                "latest_quarters": sorted(by_fiscal_year[fiscal_years_sorted[0]]['quarters']) if fiscal_years_sorted else []
            }
        }

        logger.info(f"✅ Document statistics generated successfully for {bank_symbol}")
        return statistics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating document statistics: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating document statistics: {str(e)}")

# Add debug endpoint before the main endpoints
@app.get("/debug/documents/{bank_symbol}/{fiscal_year}")
async def debug_documents(bank_symbol: str, fiscal_year: str):
    """Debug endpoint to check available documents for a bank and fiscal year"""
    try:
        # Get bank info
        bank_info = get_bank_info_by_symbol(bank_symbol)
        if not bank_info:
            return {"error": f"Bank {bank_symbol} not found"}

        bank_id = bank_info["id"]

        # Check document_metadata table
        metadata_docs = supabase.table("document_metadata").select("*").eq("fiscal_year", fiscal_year).execute()

        # Check classified_documents
        classified_docs = supabase.table("classified_documents").select("*").execute()

        # Check raw_pdfs for this bank
        raw_pdfs = supabase.table("raw_pdfs").select("*").eq("bank_id", bank_id).execute()

        return {
            "bank_info": bank_info,
            "metadata_docs_for_fiscal_year": len(metadata_docs.data),
            "metadata_docs": [{"id": d["id"], "document_type": d.get("document_type"), "pdf_url": d.get("pdf_url")} for d in metadata_docs.data],
            "total_classified_docs": len(classified_docs.data),
            "raw_pdfs_for_bank": len(raw_pdfs.data),
            "raw_pdfs": [{"id": r["id"], "pdf_url": r.get("pdf_url")} for r in raw_pdfs.data[:5]]  # Show first 5
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/financial-statistics/{bank_symbol}")
async def get_financial_statistics(bank_symbol: str, fiscal_year: str):
    """
    Get comprehensive financial statistics for a bank and fiscal year

    Returns aggregated financial data from income statement, balance sheet, and cashflow statement
    """

    try:
        logger.info(f"📊 Fetching financial statistics for {bank_symbol} - {fiscal_year}")

        # Check for English fiscal year and convert to Nepali if needed
        fiscal_years_to_check = [fiscal_year]
        try:
            year_start = int(fiscal_year.split('/')[0])
            if year_start < 2030:
                # English format, add Nepali equivalent
                nep_year = FISCAL_YEAR_CONVERSION.get(fiscal_year)
                if nep_year:
                    fiscal_years_to_check.append(nep_year)
                    logger.info(f"Also checking Nepali fiscal year: {nep_year}")
            else:
                # Nepali format, add English equivalent
                for eng_year, nep_year in FISCAL_YEAR_CONVERSION.items():
                    if nep_year == fiscal_year:
                        fiscal_years_to_check.append(eng_year)
                        logger.info(f"Also checking English fiscal year: {eng_year}")
                        break
        except (ValueError, IndexError):
            pass

        # Try to find data with any fiscal year format
        result = None
        found_fiscal_year = None
        for fy in fiscal_years_to_check:
            result = supabase.table("financial_statements").select("*").eq("bank_symbol", bank_symbol).eq("fiscal_year", fy).execute()
            if result.data:
                found_fiscal_year = fy
                logger.info(f"✅ Found data for fiscal year: {fy}")
                break

        if not result or not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"No financial data found for {bank_symbol} in fiscal year {fiscal_year}. Available formats checked: {fiscal_years_to_check}"
            )

        logger.info(f"Found {len(result.data)} records")

        # Extract and aggregate financial data from JSONB fields
        all_records = []

        for record in result.data:
            financial_data = {
                "id": record.get("id"),
                "quarter": record.get("quarter"),
                "document_type": record.get("document_type"),
                "extracted_at": record.get("extracted_at"),
                "extraction_confidence": record.get("extraction_confidence")
            }

            # Extract income statement data
            if record.get("income_statement"):
                financial_data["income_statement"] = record["income_statement"]

            # Extract balance sheet data
            if record.get("balance_sheet"):
                financial_data["balance_sheet"] = record["balance_sheet"]

            # Extract cashflow statement data
            if record.get("cashflow_statement"):
                financial_data["cashflow_statement"] = record["cashflow_statement"]

            # Extract key ratios
            if record.get("key_ratios"):
                financial_data["key_ratios"] = record["key_ratios"]

            all_records.append(financial_data)

        # Prepare response
        response_data = {
            "bank_symbol": bank_symbol,
            "bank_name": result.data[0].get("bank_name") if result.data else None,
            "fiscal_year": found_fiscal_year,
            "total_records": len(result.data),
            "records": all_records,
            "summary": {
                "annual_reports": len([r for r in result.data if r.get("quarter") is None]),
                "quarterly_reports": len([r for r in result.data if r.get("quarter") is not None]),
                "quarters_available": sorted(list(set([r.get("quarter") for r in result.data if r.get("quarter")])))
            }
        }

        logger.info(f"✅ Successfully retrieved financial statistics for {bank_symbol}")
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching financial statistics: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching financial statistics: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "financial_extraction_api:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
