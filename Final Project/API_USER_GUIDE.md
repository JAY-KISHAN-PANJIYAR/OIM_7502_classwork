# 🏦 Financial Data Extraction API - Complete User Guide

## 📖 What This API Does
This API extracts financial statements (Income Statement, Balance Sheet, Cash Flow) from Nepali bank annual and quarterly reports using AI. It's like having a smart assistant that reads bank PDFs and converts them into structured data.

**Live API URL:** https://financial-data-extraction-dwrm.onrender.com/docs

---

## 🚀 Quick Start Guide

### Step 1: Open the API Documentation
1. **Visit:** https://financial-data-extraction-dwrm.onrender.com/docs
2. You'll see a **Swagger UI** with all available endpoints
3. Each endpoint has a **"Try it out"** button for testing

### Step 2: Understanding the Interface
- **Green** = GET requests (retrieve data)
- **Orange** = POST requests (send data to extract/add)
- Click any endpoint to expand and see details

---

## 📊 Available Endpoints (APIs)

### 1. 🏠 **GET /** - API Information
**What it does:** Shows API version and available endpoints

**How to use:**
1. Click on **GET /** endpoint
2. Click **"Try it out"**
3. Click **"Execute"**
4. See API information in the response

**Response Example:**
```json
{
  "message": "Bank Financial Data Extraction API",
  "version": "1.0.0",
  "recommended_endpoint": "/extract-bytes - Faster and more reliable"
}
```

---

### 2. 🏛️ **GET /banks** - List All Banks
**What it does:** Shows all available banks in the system

**How to use:**
1. Click **GET /banks**
2. Click **"Try it out"**
3. Click **"Execute"**
4. See list of all banks with their symbols

**Response Example:**
```json
{
  "banks": [
    {
      "symbol": "ADBL",
      "bank_name": "Agriculture Development Bank Limited",
      "website": "https://www.adbl.gov.np"
    },
    {
      "symbol": "HBL",
      "bank_name": "Himalayan Bank Limited", 
      "website": "https://www.himalayanbank.com"
    }
  ]
}
```

**💡 Important:** Use the **"symbol"** field for other API calls (e.g., "ADBL", "HBL")

---

### 3. 💰 **POST /extract** - Extract Financial Data (Legacy Method)
**What it does:** Extracts financial statements from bank reports

**How to use:**
1. Click **POST /extract**
2. Click **"Try it out"**
3. Fill in the JSON request body:

**Request Format:**
```json
{
  "bank_symbol": "ADBL",
  "fiscal_year": "2078/79",
  "report_type": "annual",
  "quarter": null
}
```

**Parameter Details:**
- **bank_symbol:** Use symbols from `/banks` endpoint (e.g., "ADBL", "HBL", "NABIL")
- **fiscal_year:** Nepal fiscal year format "2078/79", "2079/80", etc.
- **report_type:** 
  - `"annual"` for yearly reports
  - `"quarterly"` for quarterly reports
- **quarter:** 
  - `null` for annual reports
  - `"Q1"`, `"Q2"`, `"Q3"`, `"Q4"` for quarterly reports

**Example Requests:**

**For Annual Report:**
```json
{
  "bank_symbol": "ADBL", 
  "fiscal_year": "2078/79",
  "report_type": "annual",
  "quarter": null
}
```

**For Quarterly Report:**
```json
{
  "bank_symbol": "HBL",
  "fiscal_year": "2080/81", 
  "report_type": "quarterly",
  "quarter": "Q1"
}
```

---

### 4. ⚡ **POST /extract-bytes** - Extract Financial Data (NEW - Faster Method)
**What it does:** Same as `/extract` but 80% faster and more reliable

**How to use:**
1. Click **POST /extract-bytes**
2. Click **"Try it out"** 
3. Use the same JSON format as `/extract`

**🎯 Recommendation:** Use this endpoint instead of `/extract` for better performance!

---

### 5. 📄 **POST /add-document** - Add New Document
**What it does:** Adds a new bank document to the system for future extraction

**How to use:**
1. Click **POST /add-document**
2. Click **"Try it out"**
3. Fill in the JSON request body:

**Request Format:**
```json
{
  "bank_symbol": "NABIL",
  "fiscal_year": "2080/81",
  "report_type": "annual", 
  "quarter": null,
  "pdf_url": "https://www.nabilbank.com/reports/annual-report-2080-81.pdf",
  "filename": "NABIL_Annual_Report_2080-81.pdf",
  "document_type": "annual_report"
}
```

**Parameter Details:**
- **pdf_url:** Direct link to the PDF file
- **filename:** Name for the file
- **document_type:** 
  - `"annual_report"` for annual reports
  - `"quarterly_report"` for quarterly reports

---

### 6. 📈 **GET /financial-data/{bank_symbol}** - Get All Bank Data  
**What it does:** Gets all extracted financial data for a specific bank

**How to use:**
1. Click **GET /financial-data/{bank_symbol}**
2. Click **"Try it out"**
3. Enter bank symbol (e.g., "ADBL") in the **bank_symbol** field
4. Click **"Execute"**

**Example:** Enter `ADBL` to get all ADBL financial data

---

## 💡 Step-by-Step Example: Extract ADBL Annual Report

### Step 1: Check Available Banks
1. Go to **GET /banks**
2. Click **"Try it out"** → **"Execute"**
3. Find ADBL in the list: `"symbol": "ADBL"`

### Step 2: Extract Financial Data
1. Go to **POST /extract-bytes** (recommended)
2. Click **"Try it out"**
3. Copy this JSON into the request body:
```json
{
  "bank_symbol": "ADBL",
  "fiscal_year": "2078/79", 
  "report_type": "annual",
  "quarter": null
}
```
4. Click **"Execute"**

### Step 3: Review Results
The API will return:
- **Income Statement** (Revenue, Expenses, Profit)
- **Balance Sheet** (Assets, Liabilities, Equity)  
- **Cash Flow Statement** (Operating, Investing, Financing activities)
- **Data Source** ("database" if cached, "extracted" if newly processed)

---

## 🔍 Understanding the Response

### Successful Response Structure:
```json
{
  "bank_symbol": "ADBL",
  "bank_name": "Agriculture Development Bank Limited",
  "fiscal_year": "2078/79",
  "quarter": null,
  "document_type": "annual_report",
  "income_statement": {
    "year": 2079,
    "interest_income": 15000000000,
    "interest_expense": 8000000000,
    "net_interest_income": 7000000000,
    // ... more fields
  },
  "balance_sheet": {
    "year": 2079, 
    "total_assets": 500000000000,
    "total_liabilities": 450000000000,
    "total_equity": 50000000000,
    // ... more fields
  },
  "cashflow_statement": {
    "year": 2079,
    "net_cash_from_operating_activities": 5000000000,
    // ... more fields
  },
  "data_source": "database", // or "extracted"
  "extraction_confidence": "high",
  "extracted_at": "2024-09-26T10:30:00"
}
```

### Key Points:
- **Numbers are in NPR** (Nepalese Rupees)
- **null values** mean data not found in the document
- **data_source: "database"** = Retrieved from cache (faster)
- **data_source: "extracted"** = Newly extracted from PDF (slower)

---

## ❌ Common Errors and Solutions

### Error 404: Bank not found
**Problem:** `Bank 'XYZ' not found`
**Solution:** Check available banks using `/banks` endpoint and use correct symbol

### Error 404: No document found  
**Problem:** `No document found for ADBL 2080/81 annual`
**Solution:** Use `/add-document` endpoint to add the document first

### Error 500: Failed to extract
**Problem:** PDF processing failed
**Solution:** 
1. Check if PDF URL is accessible
2. Try `/extract-bytes` instead of `/extract`
3. Ensure PDF is a valid bank financial report

### Invalid fiscal year format
**Problem:** API doesn't understand the year
**Solution:** Use Nepal fiscal year format: "2078/79", "2079/80", etc.

---

## 🎯 Best Practices

### 1. **Use Correct Bank Symbols**
- Always check `/banks` first to get correct symbols
- Use exactly as shown (case-sensitive): "ADBL", not "adbl"

### 2. **Choose the Right Endpoint**
- **Recommended:** Use `/extract-bytes` (faster, more reliable)
- **Legacy:** `/extract` (slower, kept for compatibility)

### 3. **Fiscal Year Format**
- Nepal format: "2078/79", "2079/80", "2080/81"
- Not: "2078", "78/79", or "2078-79"

### 4. **Check Data Source**
- `"data_source": "database"` = Instant results (cached)
- `"data_source": "extracted"` = May take 30-60 seconds (new extraction)

### 5. **Handle Quarters Properly**
- Annual reports: `"quarter": null`
- Quarterly reports: `"quarter": "Q1"` (Q1, Q2, Q3, Q4)

---

## 🔧 Testing Different Scenarios

### Test 1: Get Bank List
```
Endpoint: GET /banks
Result: List of all available banks
```

### Test 2: Extract Annual Report
```json
{
  "bank_symbol": "ADBL",
  "fiscal_year": "2078/79",
  "report_type": "annual", 
  "quarter": null
}
```

### Test 3: Extract Quarterly Report  
```json
{
  "bank_symbol": "HBL",
  "fiscal_year": "2079/80",
  "report_type": "quarterly",
  "quarter": "Q2"
}
```

### Test 4: Add New Document
```json
{
  "bank_symbol": "NABIL",
  "fiscal_year": "2080/81",
  "report_type": "annual",
  "quarter": null, 
  "pdf_url": "https://example.com/nabil-report.pdf",
  "filename": "NABIL_Annual_2080-81.pdf",
  "document_type": "annual_report"
}
```

---

## ⏱️ Performance Expectations

### Fast Response (Cached Data)
- **Time:** 1-3 seconds
- **Source:** `"data_source": "database"`
- **When:** Data already extracted previously

### Slow Response (New Extraction)
- **Time:** 30-60 seconds  
- **Source:** `"data_source": "extracted"`
- **When:** First time extracting this document

### Very Slow Response (Document Processing)
- **Time:** 60-120 seconds
- **When:** Large PDF or complex document structure

---

## 🎊 Success! You're Ready to Use the API

### What You Can Do Now:
1. ✅ **List all banks** - See what's available
2. ✅ **Extract financial data** - Get Income Statement, Balance Sheet, Cash Flow
3. ✅ **Add new documents** - Expand the database  
4. ✅ **Get historical data** - Access previously extracted data instantly
5. ✅ **Handle both annual and quarterly reports** - Complete coverage

### Next Steps:
1. Start with `/banks` to see available data
2. Try `/extract-bytes` with your favorite bank
3. Check the response structure and data quality
4. Use the data for your financial analysis needs!

**Happy Data Extraction! 🚀📊**
