"""Office exports from the same tabular dataset displayed by the preview."""
import io
import math
from decimal import Decimal


def table_rows(report):
    columns = report['columns']
    rows = [[str(index), *[row.get(column['key'], '') for column in columns]]
            for index, row in enumerate(report['rows'], 1)]
    rows.append(['Totals', *[report['totals'].get(column['key'], '') for column in columns]])
    return ['No.', *[column['label'] for column in columns]], rows


def workbook_bytes(report):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Report'
    headings, rows = table_rows(report)
    width = len(headings)
    for text in [report['organisation'], report['department'], report['title'], report['filters'],
                 f'Generated: {report["generated_at"]} · {report["count"]} records · INR']:
        sheet.append([text])
        sheet.merge_cells(start_row=sheet.max_row, start_column=1, end_row=sheet.max_row, end_column=width)
        cell = sheet.cell(sheet.max_row, 1)
        cell.data_type = 's'
        cell.alignment = Alignment(wrap_text=True, vertical='center')
        sheet.row_dimensions[sheet.max_row].height = 30 if sheet.max_row == 4 else 24
    sheet['A1'].font = Font(size=14, bold=True, color='18354B')
    sheet['A3'].font = Font(size=16, bold=True, color='18354B')
    sheet.append(headings)
    header_row = sheet.max_row
    for index, values in enumerate(rows):
        sheet.append(values)
        row_number = sheet.max_row
        for column_index, cell in enumerate(sheet[row_number], 1):
            is_money = column_index > 1 and report['columns'][column_index - 2]['numeric']
            if is_money and cell.value != '':
                cell.value = Decimal(str(cell.value))
                cell.number_format = '#,##0.00;[Red](#,##0.00)'
            elif isinstance(cell.value, str):
                cell.data_type = 's'
            cell.alignment = Alignment(wrap_text=True, vertical='top', horizontal='right' if is_money else 'left')
            if index == len(rows) - 1:
                cell.font = Font(bold=True, color='18354B')
                cell.fill = PatternFill('solid', fgColor='E8EFF4')
        lines = max(sum(max(1, math.ceil(len(line) / (26 if column_index == 1 else 17)))
                        for line in str(value).split('\n'))
                    for column_index, value in enumerate(values))
        sheet.row_dimensions[row_number].height = max(32, lines * 14)
    total_row = sheet.max_row
    for note in report['notes']:
        sheet.append([note])
        sheet.merge_cells(start_row=sheet.max_row, start_column=1, end_row=sheet.max_row, end_column=width)
        sheet.cell(sheet.max_row, 1).alignment = Alignment(wrap_text=True, vertical='top')
        sheet.cell(sheet.max_row, 1).data_type = 's'
        sheet.row_dimensions[sheet.max_row].height = 32
    for cell in sheet[header_row]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='18354B')
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    sheet.row_dimensions[header_row].height = 32
    sheet.column_dimensions['A'].width = 6
    for index, column in enumerate(report['columns'], 2):
        sheet.column_dimensions[get_column_letter(index)].width = 28 if column['key'] == 'vendor' else 19
    sheet.freeze_panes = f'C{header_row + 1}'
    sheet.auto_filter.ref = f'A{header_row}:{get_column_letter(width)}{max(header_row, total_row - 1)}'
    sheet.print_title_rows = f'1:{header_row}'
    sheet.print_options.horizontalCentered = True
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = 'landscape'
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth, sheet.page_setup.fitToHeight = 1, 0
    sheet.oddFooter.center.text = 'Page &P of &N'
    sheet.print_area = f'A1:{get_column_letter(width)}{sheet.max_row}'
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def document_bytes(report):
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    document = Document()
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = Inches(11.69), Inches(8.27)
    section.top_margin = section.bottom_margin = Inches(0.5)
    section.left_margin = section.right_margin = Inches(0.45)
    normal = document.styles['Normal']
    normal.font.name, normal.font.size = 'Calibri', Pt(9)
    normal.paragraph_format.space_after = Pt(5)
    document.add_heading(report['organisation'], level=1)
    document.add_paragraph(report['department'])
    document.add_heading(report['title'], level=2)
    document.add_paragraph(report['filters'])
    document.add_paragraph(f'Generated: {report["generated_at"]} · {report["count"]} records · All amounts in INR')
    headings, rows = table_rows(report)
    table = document.add_table(rows=1, cols=len(headings))
    table.style = 'Table Grid'
    table.autofit = False
    available = section.page_width - section.left_margin - section.right_margin
    weights = [0.45, *[2 if column['key'] == 'vendor' else 1.25 if column['key'] in ('dispatch_ref_no', 'receipt_status', 'receipt') else 1
                       for column in report['columns']]]
    for column, weight in zip(table.columns, weights):
        column.width = int(available * weight / sum(weights))
    for cell, label in zip(table.rows[0].cells, headings):
        cell.text = label
        shade = OxmlElement('w:shd')
        shade.set(qn('w:fill'), '18354B')
        cell._tc.get_or_add_tcPr().append(shade)
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.color.rgb = RGBColor.from_string('FFFFFF')
    for cell, column in zip(table.rows[0].cells, table.columns):
        cell.width = column.width
    repeat = OxmlElement('w:tblHeader')
    table.rows[0]._tr.get_or_add_trPr().append(repeat)
    for index, values in enumerate(rows):
        row = table.add_row()
        row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        for column_index, (cell, value) in enumerate(zip(row.cells, values)):
            cell.width = table.columns[column_index].width
            cell.text = str(value)
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(3)
            if column_index and report['columns'][column_index - 1]['numeric']:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for run in paragraph.runs:
                run.font.size = Pt(8)
                run.bold = index == len(rows) - 1
    if not report['rows']:
        document.add_paragraph('No records match these filters.')
    for note in report['notes']:
        document.add_paragraph(note)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run('Page ')
    field = OxmlElement('w:fldSimple')
    field.set(qn('w:instr'), 'PAGE')
    footer._p.append(field)
    document.core_properties.title = report['title']
    document.core_properties.author = report['organisation']
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()
