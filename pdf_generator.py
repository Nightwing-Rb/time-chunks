import io
import base64
from typing import List
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, 
    Table, TableStyle, ListFlowable, ListItem, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

from models import Chunk

# Custom style setup
styles = getSampleStyleSheet()

# Update standard styles to look modern
styles['Normal'].fontName = 'Helvetica'
styles['Normal'].fontSize = 11
styles['Normal'].leading = 16
styles['Normal'].spaceAfter = 12

styles['Heading1'].fontName = 'Helvetica-Bold'
styles['Heading1'].fontSize = 20
styles['Heading1'].leading = 24
styles['Heading1'].spaceBefore = 20
styles['Heading1'].spaceAfter = 15

styles['Heading2'].fontName = 'Helvetica-Bold'
styles['Heading2'].fontSize = 16
styles['Heading2'].leading = 20
styles['Heading2'].spaceBefore = 15
styles['Heading2'].spaceAfter = 10

styles['Heading3'].fontName = 'Helvetica-Bold'
styles['Heading3'].fontSize = 13
styles['Heading3'].leading = 16
styles['Heading3'].spaceBefore = 10
styles['Heading3'].spaceAfter = 8

styles.add(ParagraphStyle(
    name='ChunkHeader',
    fontName='Helvetica-Bold',
    fontSize=14,
    textColor=colors.white,
    backColor=colors.black,
    alignment=1, # Center
    spaceBefore=0,
    spaceAfter=25,
    borderPadding=10
))

styles.add(ParagraphStyle(
    name='Caption',
    parent=styles['Normal'],
    fontName='Helvetica-Oblique',
    fontSize=9,
    textColor=colors.dimgrey,
    alignment=1, # Center
    spaceBefore=5,
    spaceAfter=15
))

styles.add(ParagraphStyle(
    name='TOCItem',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=12,
    spaceBefore=5,
    spaceAfter=5
))


def generate_single_pdf(chunks: List[Chunk]) -> io.BytesIO:
    """
    Generates a single PDF in memory. 
    Page 1: Table of contents
    Subsequent pages: Chunks, separated by hard page breaks.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    story = []
    
    # --- PAGE 1: Table of Contents ---
    story.append(Paragraph("Reading Chunks", styles['Heading1']))
    story.append(Paragraph("Table of Contents", styles['Heading2']))
    story.append(Spacer(1, 10))
    
    for chunk in chunks:
        minutes = chunk.estimated_minutes
        words = chunk.total_words
        label = f"Chunk {chunk.chunk_number} — {minutes} min read ({words} words)"
        story.append(Paragraph(label, styles['TOCItem']))
    
    story.append(PageBreak())
    
    
    # --- CHUNK PAGES ---
    total_chunks = len(chunks)
    
    for chunk in chunks:
        # 1. Chunk Banner Header
        header_text = f"Chunk {chunk.chunk_number} of {total_chunks} — ~{chunk.estimated_minutes} min read"
        story.append(Paragraph(header_text, styles['ChunkHeader']))
        
        # 2. Iterate Elements
        current_list_items = []
        current_list_style = 'bullet'
        
        # Helper to flush pending lists
        def flush_list():
            nonlocal current_list_items
            if current_list_items:
                lf = ListFlowable(
                    [ListItem(Paragraph(li, styles['Normal'])) for li in current_list_items],
                    bulletType='bullet' if current_list_style == 'bullet' else '1',
                    leftIndent=15,
                    spaceAfter=15
                )
                story.append(lf)
                current_list_items = []
        
        for element in chunk.elements:
            etype = element.type
            
            # If we were building a list but the next element isn't a list item, flush
            if etype != 'list_item' and current_list_items:
                flush_list()
                
            if etype == 'paragraph':
                story.append(Paragraph(element.content, styles['Normal']))
                
            elif etype == 'heading':
                level = element.heading_level or 1
                # clamp between 1 and 3
                level = max(1, min(level, 3))
                h_style = styles[f'Heading{level}']
                story.append(Paragraph(element.content, h_style))
                
            elif etype == 'caption':
                story.append(Paragraph(element.content, styles['Caption']))
                
            elif etype == 'table' and element.table_data:
                # Build Reportlab Table
                # Provide paragraph wrappers for cells to allow text wrapping inside cells
                wrapped_data = []
                for row_idx, row in enumerate(element.table_data):
                    wrapped_row = []
                    for cell_text in row:
                        # minimal style for table cells
                        p = Paragraph(str(cell_text), styles['Normal'])
                        wrapped_row.append(p)
                    wrapped_data.append(wrapped_row)
                
                t = Table(wrapped_data, colWidths=[(doc.width / len(wrapped_data[0]))] * len(wrapped_data[0]))
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                    ('TOPPADDING', (0,0), (-1,-1), 8),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ]))
                story.append(t)
                story.append(Spacer(1, 15))
                
            elif etype == 'list_item':
                current_list_style = element.list_style or 'bullet'
                current_list_items.append(element.content)
                
            elif etype == 'image' and element.image_source:
                try:
                    # The base64 string might have data URI prefix like "data:image/jpeg;base64,...", handle it just in case
                    b64_data = element.image_source
                    if b64_data.startswith("data:image"):
                        b64_data = b64_data.split(",", 1)[-1]
                        
                    img_bytes = base64.b64decode(b64_data)
                    img_buffer = io.BytesIO(img_bytes)
                    img = Image(img_buffer)
                    
                    # Constrain image size to page width margins
                    avail_width = doc.width
                    if img.drawWidth > avail_width:
                        scaling_factor = avail_width / img.drawWidth
                        img.drawWidth = avail_width
                        img.drawHeight = img.drawHeight * scaling_factor
                        
                    story.append(Spacer(1, 10))
                    story.append(img)
                    story.append(Spacer(1, 15))
                except Exception as e:
                    # Fallback if image errors out
                    story.append(Paragraph(f"[Figure: Unable to render image - {str(e)}]", styles['Caption']))

        # Catch trailing list at the end of the chunk
        flush_list()
        
        # Hard break between chunks except the last one
        if chunk.chunk_number < total_chunks:
            story.append(PageBreak())

    # Build PDF
    doc.build(story)
    
    # Prepare buffer for streaming
    buffer.seek(0)
    return buffer
