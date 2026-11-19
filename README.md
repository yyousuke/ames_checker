# NASA Ames ASCII Exchange File Validator

日本語 / English

## 概要 / Overview

このユーティリティは、NASA Ames ASCII 形式のファイルが分析やデータ処理の前に構造的に妥当かどうかを確認するためのツールです。

This utility checks whether a NASA Ames ASCII format file is structurally valid before it is used in analysis or data processing.

スクリプトは実用的な用途を想定しており、ファイル形式の確認、破損したレコードの検出、ヘッダーやデータ部の不整合の指摘を行います。これにより、後段の処理で想定外の失敗が起きる前に、一般的な書式上の問題を早期に発見できます。

The script is intended for practical use: it verifies the file format, detects malformed records, and highlights invalid header or data-block structure. It is designed to catch common formatting issues early so that downstream processing does not fail unexpectedly.

## 1. 検査内容 / What this tool checks

このバリデータが確認する主な項目は次のとおりです。

The validator inspects the file for the following issues:

- 非表示 ASCII 文字 / Non-printable ASCII characters
- タブ文字 / Tab characters
- 許容長さを超える行 / Lines that exceed the allowed length
- `NLHEAD` や `FFI` などの不正なヘッダー値 / Invalid header values such as `NLHEAD` and `FFI`
- レコード順序の不一致または不足 / Incorrect record ordering or missing required entries
- 日付の不正 / Invalid date values
- 未対応または未知の FFI / Unsupported or unknown FFI identifiers
- 変数数や補助メタデータの不整合 / Inconsistent variable counts and auxiliary metadata
- 各対応 FFI に対するデータ部の構造エラー / Data-section structure errors for each supported FFI
- Version 2 メタデータの不整合 / Version 2 metadata inconsistencies

このツールは構造検証に重点を置いており、ファイルが仕様に沿って整形されているかを確認します。ただし、科学的な値そのものが物理的・気象学的に妥当であることまでは保証しません。

This tool is focused on structural validation. It checks whether the file follows the expected format rules, but it does not guarantee that the scientific content itself is physically or meteorologically correct.

## 2. 対応している FFI / Supported file types

このバリデータが対応する FFI は次のとおりです。

This validator supports the following FFI values:

- 1001
- 1010
- 1020
- 2010
- 2110
- 2160
- 2310
- 3010
- 4010

対応していない FFI を含む場合、スクリプトはエラーを出力します。

If the file uses an unsupported FFI, the script reports an error.

## 3. 実行方法 / How to run it

コマンドラインから次のように実行します。

From the command line, run:

```bash
python nasa_ames_validator.py <file_path>
```

例:

For example:

```bash
python nasa_ames_validator.py sample_ames.txt
```

## 4. 終了コード / Exit status

スクリプト実行後は終了コードを返します。

When the script finishes, it returns an exit code:

- 0: 正常終了、構造エラーなし / 0: validation passed, no structural errors found
- 1: エラーまたは警告があり検証失敗 / 1: validation failed due to one or more errors or warnings
- 2: 入力ファイルが見つからない / 2: input file was not found

## 5. 出力形式 / Output format

検査結果は標準出力に表示されます。

The validator prints messages directly to the terminal.

- 警告は `WARN` で始まります / Warning messages start with `WARN`
- エラーは `ERROR` で始まります / Error messages start with `ERROR`
- 正常時は次のメッセージで終了します / A successful validation ends with:

```text
OK: no structural format errors found.
```

出力例:

Example output:

```text
[ERROR] line 15: Unsupported/unknown FFI: 9999
[WARN] line 32: Numeric record line has no parseable numeric tokens
```

## 6. 主な検査ルール / Typical validation rules

### 6.1 ASCII 文字チェック / ASCII validity

ファイルは有効な printable ASCII のみで構成する必要があります。検証対象となるのは次のような問題です。

The file must contain only valid printable ASCII characters. The validator rejects:

- 制御文字 / control characters
- タブ文字 / tab characters
- 最大長を超える行 / lines exceeding the maximum length

### 6.2 ヘッダー検査 / Header checks

スクリプトはヘッダーを読み取り、最初の数値が `NLHEAD` と `FFI` に対応しているかを確認します。さらに、必要な文字列レコードや数値レコードが正しい順序で存在するかも確認します。

The script reads the header and verifies the first numeric entries corresponding to `NLHEAD` and `FFI`. It then checks that the required string and numeric records appear in the correct order.

### 6.3 FFI ごとの規則 / FFI-specific rules

各 FFI には異なる構造要件があります。バリデータは次の値を確認します。

Each FFI has different structural requirements. The validator checks values such as:

- `IVOL` と `NVOL` が正の整数であるか / whether `IVOL` and `NVOL` are positive integers
- 必要な `DX` が存在するか / whether required `DX` values are present
- `NX` と `NXDEF` が一貫しているか / whether `NX` and `NXDEF` are consistent
- `NAUXV` が負でないか / whether `NAUXV` is non-negative

### 6.4 データ部の検査 / Data section checks

スクリプトはデータレコードを順に読み取り、各 FFI に対して必要な長さと件数が満たされているかを確認します。また IVM 値が単調増加または単調減少であるかも確認し、同じ値が連続している場合は不正とします。

The script reads the data records and validates their lengths and counts according to each FFI. It also checks whether the IVM values are properly monotonic: they must be strictly increasing or strictly decreasing.

## 7. 推奨される使い方 / Recommended usage

このツールは、解析や変換、科学計算の前に行う事前チェックとして最適です。

This tool is best used as a preliminary validation step before analysis, conversion, or scientific processing.

出力にエラーがなければ、ファイルは NASA Ames 形式として構造的に整っていると判断できます。エラーが出た場合は、問題が発生した箇所と種類がメッセージとして示されます。

If the output reports no errors, the file is structurally consistent with the expected NASA Ames format. If errors are reported, the message indicates where the problem is located and what type of issue was detected.

## 8. 実行例 / Example

```bash
python nasa_ames_validator.py /path/to/input.ames
```

ファイルが正常な場合は次の出力が表示されます。

If the file is valid, you will see:

```text
OK: no structural format errors found.
```

ファイルが不正な場合は、該当行番号と詳細なエラーメッセージが出力されます。

If the file is invalid, the validator will print the relevant line number and a detailed message describing the issue.

## 9. 補足 / Notes

- このツールは科学的な妥当性ではなく、ファイル構造の妥当性を検証します。
- このツールはデータ解析の前段での品質管理に適しています。
- 壊れたヘッダー、不完全なレコード、互換性のないレイアウトを検出するのに有効です。

- This tool validates file structure, not scientific correctness.
- It is suitable for quality control before data analysis.
- It is especially useful for catching broken headers, incomplete records, and incompatible file layouts.

---

## 謝辞 / Acknowledgements

このツールで用いているデータ形式と検証項目を整理しPythonへ変換する作業は、GitHub Copilot（Claude Sonnet 5モデル>使用）の支援を受けて行われました。

GitHub Copilot (Claude Sonnet 5 model) was used to assist in organizing the data formats and validation items used in this tool and converting them into Python.

