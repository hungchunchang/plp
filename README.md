# pLp: PDF Literature Processor

A VS Code extension that automatically processes PDF literature files into organized research notes.

## Features

- **PDF Processing**: Extract bibliographic information from PDF files
- **Automatic Citation**: Generate BibTeX citations using DOI or OpenAI
- **Custom Templates**: Use your own Markdown templates
- **File Organization**: Rename PDFs with standardized naming convention
- **Batch Processing**: Process entire folders of PDFs

## Installation

1. Download the `.vsix` file
2. Open VS Code
3. Go to Extensions → "..." → Install from VSIX
4. Select the downloaded file

## Usage

### Process Single PDF

- Right-click on a PDF file → "Process Single PDF"
- Or use Command Palette (`Cmd+Shift+P`) → "PDF Processor: Process Single PDF"

### Process Folder

- Right-click on a folder → "Process PDF Folder"
- Or use Command Palette → "PDF Processor: Process PDF Folder"

## Configuration

Open VS Code settings and search for "PDF Processor":

- **Output Path**: Where to save processed files (default: `~/Downloads/PDF_Output`)
- **Template Path**: Custom Markdown template file (optional)
- **OpenAI API Key**: For title extraction when DOI not found
- **Bibtex Path**: Custom BibTeX file name

### Set Paths via Commands

- `PDF Processor: Select Output Directory`
- `PDF Processor: Select Template File`
- `PDF Processor: Select Bibtex File`

## Template Variables

If using custom templates, include these variables:

- `{{title}}` - Paper title
- `{{bibtex}}` - Generated BibTeX citation
- `{{date}}` - Current date

## Requirements

- Python 3.7+
- Required Python packages (auto-installed):
  - `openai`
  - `pypdf`
  - `requests`
  - `python-dotenv`

## Output

For each PDF, generates:

- Renamed PDF file (e.g., `smith2023machine.pdf`)
- Markdown note file (e.g., `smith2023machine.md`)
- BibTeX entry in `reference.bib`

## Troubleshooting

**Permission Issues**: Ensure output directory is writable. Change output path in settings if needed.

**Missing Citations**: Add OpenAI API key for better title extraction.

**Python Errors**: Check Python installation and internet connection.

## License

MIT

## Contributing

Report issues and feature requests on GitHub.