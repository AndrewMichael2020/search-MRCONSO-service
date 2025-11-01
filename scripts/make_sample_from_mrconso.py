#!/usr/bin/env python3
"""
Generate a synthetic MRCONSO-like sample file.
Can also extract from a real MRCONSO.RRF if you have a UMLS license.
"""
import argparse
import random
import sys


def generate_synthetic_terms(n=50000):
    """Generate synthetic medical-like terms."""
    # Common medical prefixes and suffixes
    prefixes = [
        "hyper", "hypo", "anti", "pre", "post", "sub", "inter", "intra", 
        "trans", "retro", "peri", "para", "meta", "syn", "epi", "endo",
        "cardio", "neuro", "gastro", "hepato", "nephro", "pulmo", "osteo",
        "hemo", "derma", "myo", "arterio", "veno", "pneumo", "rhino"
    ]
    
    roots = [
        "cardi", "neur", "gastr", "hepat", "nephr", "pulmon", "oste",
        "hem", "derm", "my", "arteri", "ven", "pneum", "rhin", "cephal",
        "thromb", "cyt", "leuk", "erythr", "plasm", "carcin", "aden",
        "path", "tox", "scler", "sten", "malaci", "megaly", "plas",
        "trophy", "algi", "cele", "centesis", "ectomy", "ostomy", "otomy"
    ]
    
    suffixes = [
        "itis", "osis", "emia", "pathy", "trophy", "algia", "plasty",
        "ectomy", "otomy", "ostomy", "scopy", "graphy", "meter", "logy",
        "gram", "penia", "cytosis", "iasis", "oma", "trophy", "plasia",
        "stenosis", "megaly", "cele", "centesis", "pexy", "rhaphy", "stasis"
    ]
    
    terms = set()
    
    # Generate complex medical terms
    while len(terms) < n:
        # Various patterns
        pattern = random.choice([1, 2, 3, 4])
        
        if pattern == 1:
            # prefix + root + suffix
            term = random.choice(prefixes) + random.choice(roots) + random.choice(suffixes)
        elif pattern == 2:
            # root + suffix
            term = random.choice(roots) + random.choice(suffixes)
        elif pattern == 3:
            # prefix + root
            term = random.choice(prefixes) + random.choice(roots)
        else:
            # double root + suffix
            term = random.choice(roots) + random.choice(roots) + random.choice(suffixes)
        
        terms.add(term.capitalize())
    
    return list(terms)


def extract_from_mrconso(mrconso_path, n=50000):
    """Extract terms from real MRCONSO.RRF file."""
    terms = []
    
    try:
        with open(mrconso_path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                parts = line.strip().split('|')
                if len(parts) > 14:
                    term = parts[14].strip()
                    if term:
                        terms.append(term)
    except FileNotFoundError:
        print(f"Error: MRCONSO file not found at {mrconso_path}", file=sys.stderr)
        sys.exit(1)
    
    return terms


def write_mrconso_sample(terms, output_path):
    """Write terms in MRCONSO.RRF format (pipe-delimited with 15+ fields)."""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, term in enumerate(terms):
            # Create a fake MRCONSO row with the term at index 14
            # Format: CUI|LAT|TS|LUI|STT|SUI|ISPREF|AUI|SAUI|SCUI|SDUI|SAB|TTY|CODE|STR|SRL|SUPPRESS|CVF
            cui = f"C{i:07d}"
            lat = "ENG"
            ts = "P"
            lui = f"L{i:07d}"
            stt = "PF"
            sui = f"S{i:07d}"
            ispref = "Y"
            aui = f"A{i:08d}"
            saui = ""
            scui = ""
            sdui = ""
            sab = "SNOMEDCT_US"
            tty = "PT"
            code = f"{i:06d}"
            str_term = term
            srl = "0"
            suppress = "N"
            cvf = ""
            
            row = f"{cui}|{lat}|{ts}|{lui}|{stt}|{sui}|{ispref}|{aui}|{saui}|{scui}|{sdui}|{sab}|{tty}|{code}|{str_term}|{srl}|{suppress}|{cvf}"
            f.write(row + '\n')


def main():
    parser = argparse.ArgumentParser(
        description='Generate synthetic MRCONSO sample or extract from real file'
    )
    parser.add_argument(
        '--mrconso', 
        help='Path to real MRCONSO.RRF file (if you have UMLS license)'
    )
    parser.add_argument(
        '--out', 
        default='data/mrconso_sample.txt',
        help='Output path for sample file (default: data/mrconso_sample.txt)'
    )
    parser.add_argument(
        '--n', 
        type=int, 
        default=50000,
        help='Number of terms to generate/extract (default: 50000)'
    )
    
    args = parser.parse_args()
    
    if args.mrconso:
        print(f"Extracting {args.n} terms from {args.mrconso}...")
        terms = extract_from_mrconso(args.mrconso, args.n)
    else:
        print(f"Generating {args.n} synthetic medical terms...")
        terms = generate_synthetic_terms(args.n)
    
    print(f"Writing {len(terms)} terms to {args.out}...")
    write_mrconso_sample(terms, args.out)
    print("Done!")


if __name__ == '__main__':
    main()
