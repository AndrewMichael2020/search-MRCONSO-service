# Data Directory

This directory contains MRCONSO-like sample data for the BK-tree fuzzy search application.

## Files

- `mrconso_sample.txt` - Generated sample data in pipe-delimited format (not committed to git)

## Format

The sample data follows the MRCONSO.RRF format from UMLS Metathesaurus:

```
CUI|LAT|TS|LUI|STT|SUI|ISPREF|AUI|SAUI|SCUI|SDUI|SAB|TTY|CODE|STR|SRL|SUPPRESS|CVF
```

Where:
- **Field 14 (STR)** - The medical term string (0-indexed)
- Each line contains 18 pipe-delimited fields
- The application extracts and indexes the STR field

## Generating Sample Data

### Synthetic Data (No UMLS License Required)

```bash
python scripts/make_sample_from_mrconso.py --out data/mrconso_sample.txt --n 50000
```

This generates 50,000 synthetic medical-like terms.

### Real MRCONSO Data (UMLS License Required)

If you have a UMLS license:

1. Download MRCONSO.RRF from the [NLM UMLS Portal](https://www.nlm.nih.gov/research/umls/)
2. Extract terms using:

```bash
python scripts/make_sample_from_mrconso.py \
  --mrconso path/to/MRCONSO.RRF \
  --out data/mrconso_sample.txt \
  --n 50000
```

## Important Notes

- **DO NOT commit MRCONSO.RRF files** - they are protected by UMLS license
- The `.gitignore` file excludes `*.RRF` files automatically
- Sample data is regenerated during CI/CD builds
- For production use, ensure compliance with UMLS licensing terms

## Privacy & Security

- Use only synthetic data or properly licensed UMLS data
- Do not include any PHI (Protected Health Information)
- Sample data is for demonstration and benchmarking only
