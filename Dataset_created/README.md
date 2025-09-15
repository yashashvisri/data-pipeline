# Indian Kanoon Scraper(Using Crawling) & Synthetic Data Generator

## Project Overview

This project contains two primary components for working with legal case data:

1.  **A Real Data Scraper:** A two-stage pipeline that automates the downloading of real legal documents from the Indian Kanoon website and parses them into a structured format.
2.  **A Synthetic Data Generator:** A tool to create a large, realistic-looking dataset of fake legal cases, which is useful for testing, development, or machine learning tasks.

---

## Part 1: Real Data Scraping & Parsing Workflow

This workflow is designed to reliably collect and structure actual case documents from the web. It operates in two distinct stages to ensure accuracy and stability.

### **Stage 1: Bulk PDF Downloading**

The first stage focuses entirely on getting the source files from the internet onto your local computer.

-   The process begins with a script that automates a web browser using **Selenium**.
-   You provide the script with a search URL from the Indian Kanoon website.
-   The script navigates to the URL, finds all the links to individual case documents across the number of pages you specify, and systematically downloads each document as a **PDF file**.
-   All downloaded PDFs are saved into a single folder on your local machine (e.g., `downloaded_pdfs`), creating a local repository of documents to work with.

### **Stage 2: Offline PDF Parsing**

The second stage works entirely offline, using the PDFs you downloaded in Stage 1.

-   A separate parser script reads and processes each PDF from your local folder.
-   It uses the **PyMuPDF** library to extract the full, raw text from inside each document.
-   The script then applies an **intelligent, section-based parsing** logic. It searches the text for common legal headings (like "Facts of the case," "Issues," and "Conclusion") to identify and separate the key parts of the judgment.
-   This method is highly effective at structuring the unstructured text of the legal document.
-   The final, structured data is then saved into clean, easy-to-use **JSON** files.

---

## Part 2: Synthetic Legal Data Generation

This workflow is used when you need a large amount of realistic but completely artificial legal data for testing or analysis, without needing to scrape the web.

### **The Process**

-   This is handled by a single Python script that uses a `FakeCaseGenerator` class.
-   The script leverages the **Faker** library to generate plausible but entirely unreal data points.
-   It creates a specified number of cases (e.g., 300) and, for each case, it generates:
    -   Randomized court names, case numbers, and judgment dates.
    -   Plausible petitioner, respondent, and judge names, using a locale for Indian names.
    -   Realistic, multi-sentence paragraphs for key sections like **Facts**, **Issues**, and **Conclusion**.
-   The final output is a large, consistent dataset that mimics the structure of the real scraped data.

### **The Output**

The script saves the 300 synthetic cases directly into **JSON** files, which are immediately ready for use in reports, data analysis tools, or machine learning models.
