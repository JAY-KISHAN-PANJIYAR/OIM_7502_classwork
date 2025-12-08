# 🔗 Project URL & Access Credentials

**Live URL:** [https://dev.sran.com.np/](https://dev.sran.com.np/)
**Username:** sran
**Password:** AYZKFPChRHixVi4p

---

# 🏦 Financial Data Extraction API - Complete User Guide

## 📖 What This API Does

This API extracts financial statements (Income Statement, Balance Sheet, Cash Flow) from Nepali bank annual and quarterly reports using AI. It's like having a smart assistant that reads bank PDFs and converts them into structured data.

**Live API URL:** [https://financial-data-extraction-dwrm.onrender.com/docs](https://financial-data-extraction-dwrm.onrender.com/docs)

---

## 🚀 Quick Start Guide

### Step 1: Open the API Documentation

1. **Visit:** [https://financial-data-extraction-dwrm.onrender.com/docs](https://financial-data-extraction-dwrm.onrender.com/docs)
2. You'll see a **Swagger UI** with all available endpoints
3. Each endpoint has a **"Try it out"** button for testing

### Step 2: Understanding the Interface

* **Green** = GET requests (retrieve data)
* **Orange** = POST requests (send data to extract/add)
* Click any endpoint to expand and see details

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

```json
{
  "bank_symbol": "ADBL",
  "fiscal_year": "2078/79",
  "report_type": "annual",
  "quarter": null
}
```

**Parameter Details:**

* **bank_symbol:** Use symbols from `/banks` endpoint
* **fiscal_year:** Nepal fiscal year format
* **report_type:** "annual" or "quarterly"
* **quarter:** null for annual; Q1–Q4 for quarterly

---

### 4. ⚡ **POST /extract-bytes** - Faster Extraction Method

Recommended for performance.

Uses same format as `/extract` but executes much faster.

---

### 5. 📄 **POST /add-document** - Add a New Document

Allows adding a bank report for extraction.

```json
{
  "bank_symbol": "NABIL",
  "fiscal_year": "2080/81",
  "report_type": "annual",
  "quarter": null,
  "pdf_url": "https://example.com/nabil.pdf",
  "filename": "NABIL_Report.pdf",
  "document_type": "annual_report"
}
```

---

### 6. 📈 **GET /financial-data/{bank_symbol}**

Fetches all extracted data for a specific bank.

---

## 🔍 Understanding the Response

Example response includes:

* Income Statement
* Balance Sheet
* Cash Flow Statement
* Confidence score
* Data source (database or extracted)

---

## ❌ Common Errors

* **404 Bank not found** → Check `/banks`
* **404 Document missing** → Add via `/add-document`
* **500 Extraction failed** → Try `/extract-bytes`

---

