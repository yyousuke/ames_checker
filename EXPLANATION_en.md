# NASA Ames Format Validator: Explanation

## 1. Name

Pre-publication Structural Validation Program for NASA Ames Format Data

## 2. Technical Field

This program concerns data quality management for scientific data obtained from aircraft observations, ground-based observations, numerical models, and other sources when those data are published or shared. It automatically checks file-structure conformance during the preprocessing stage in which data produced by different instruments, observation platforms, or analysis systems are prepared in the common NASA Ames ASCII exchange format.

## 3. Background and Challenges

Observation data can differ by source in header layout, number of variables, record arrangement, and the handling of missing values and auxiliary variables. If format defects or inconsistencies in declared counts are discovered after publication or during use, loading failures, manual corrections, and reprocessing may be required, reducing the efficiency of data publication and reuse. In addition, when users apply different methods to check formats, it becomes difficult to compare and integrate datasets programmatically.

NASA Ames format is a self-describing ASCII exchange format whose header records information such as the investigator, data source, variables, units, and missing values in addition to the data itself. Its standardized record structure supports the exchange and machine processing of data from different sources. This program aims to detect format problems early in pre-publication workflows that use this common format.

## 4. Program Overview

The program reads an input NASA Ames ASCII file and checks character representation, header structure, consistency between header counts and the actual structure, and data-record layout against NASA Ames Format Specification v2.0. It reports the type of issue and, where applicable, the line number so that publication staff can decide whether corrections are needed.

The supported File Format Index (FFI) values are 1001, 1010, 1020, 2010, 2110, 2160, 2310, 3010, and 4010. Because header and data-record layouts vary by FFI, the validator applies the parsing rules for the identified FFI.

## 5. Main Operations

1. Reads the input file as ASCII and checks basic constraints: printable ASCII characters, absence of tab characters, and a maximum of 132 characters per line.
2. Reads the header in the prescribed order, including NLHEAD and FFI at the beginning; string records for the investigator, organization, source, and mission; volume information; and observation and revision dates. It checks basic conditions such as whether dates are valid, values that must be integers are integers, and values meet positive or non-negative requirements.
3. Reads FFI-specific descriptions of independent variables, dependent variables, auxiliary variables, and array dimensions. It checks values such as NX, NXDEF, NAUXV, NAUXC, and NV for consistency with subsequent header records. It also attempts to read the required values and strings in variable-length header sections.
4. Compares the header-line count declared by NLHEAD with the number of header lines actually parsed. It then reads the data section according to each FFI's record rules and detects issues such as missing variable values, inconsistent records, and insufficient data at the end of the input.
5. For data with numeric Independent Variable Marks (IVMs), checks that values are not repeated and change consistently in either an increasing or decreasing direction. For FFI=2160, which uses string IVMs, it reports a warning when a string's length differs from its declared length.
6. When the designated Normal Comment metadata indicating the Version 2 extension appears at the beginning, checks the basic format and values of the format version and NIVM declarations.
7. Classifies and displays errors and warnings. If there are no errors, the validator exits with no structural errors reported, allowing publication staff to use the automated result as part of their pre-processing review record.

## 6. Expected Benefits

- Detecting format defects before publication can help reduce loading failures and manual corrections after publication.
- Applying the same validation method to datasets prepared in the common NASA Ames format enables consistent pre-publication quality checks across datasets.
- Machine-checking the header and data-section structure can reveal inconsistencies in line counts, variable counts, array dimensions, and record order that may be missed during visual inspection.
- Messages identifying problem locations can make correction requests to data creators and follow-up checks more efficient.
- Supporting publication of structured, self-describing data helps establish a foundation for discovering, loading, reanalyzing, and reusing observation data from different sources.

These benefits do not result from automatically converting data into NASA Ames format. They result from adding validation to the workflow that prepares data in the common format, making it possible to check format conformance before publication.

## 7. Technical Position and Scope

This program is a structural validator for files that have already been created in NASA Ames format. It does not convert input data, automatically generate headers or variable descriptions, convert units, correct missing values, or assess the physical or meteorological validity of observations. For the Version 2 extension, it does not comprehensively assess the meaning of all metadata or conformance of every variable description; it performs basic checks on the designated leading metadata declarations.

Therefore, a passing result indicates a preliminary check of file structure only. It does not guarantee scientific accuracy or completeness, appropriate units, rights clearance, or suitability for publication. Use it as a format-quality check in pre-publication workflows, together with human review of the content and other quality-control procedures.

## 8. Relationship to the Specification

The program was implemented with reference to the ASCII constraints, header concepts, FFI-specific file structures, and Version 2 metadata declarations described in NASA Ames Format Specification v2.0.

- Reference specification: [NASA Ames Format Specification (v2.0)](https://airbornescience.nasa.gov/content/Ames_Format_Specification_v20)
- Implementation: [`nasa_ames_validator.py`](./nasa_ames_validator.py)
