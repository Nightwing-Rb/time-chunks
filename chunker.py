from typing import List
from models import FlattenedElement, Chunk

def generate_chunks(elements: List[FlattenedElement], words_per_minute: int, duration_minutes: float) -> List[Chunk]:
    """
    Groups elements into chunks based on reading time limit.
    Implements a two-tier soft/hard limit with look-ahead to optimize chunk breaks,
    and folds small 'runt' chunks into previous chunks.
    """
    target_words = int(words_per_minute * duration_minutes)
    max_words = int(target_words * 1.25) # Hard ceiling
    large_block_ratio = 0.25
    min_chunk_words = 50
    heading_min = int(target_words * 0.5) # Break if we encounter a heading and already have half a chunk
    
    chunks: List[Chunk] = []
    current_elements: List[FlattenedElement] = []
    current_words = 0
    
    def flush_chunk():
        nonlocal current_elements, current_words
        if not current_elements:
            return
            
        chunks.append(Chunk(
            chunk_number=len(chunks) + 1,
            elements=list(current_elements),
            total_words=current_words,
            estimated_minutes=round(current_words / float(words_per_minute), 1)
        ))
        current_elements.clear()
        current_words = 0

    for element in elements:
        bwords = element.word_count
        btype = element.type
        
        # Rule: Images don't trigger anything, they just attach to the current chunk
        
        # Rule: Heading anchor break
        if btype == "heading" and current_words >= heading_min:
            flush_chunk()
            
        # Rule: Look-ahead early stop
        projected = current_words + bwords
        if current_elements:
            if projected > max_words:
                flush_chunk()
            elif projected > target_words:
                if bwords > target_words * large_block_ratio:
                    flush_chunk()
                    
        # Rule: Add atomically
        current_elements.append(element)
        current_words += bwords

    flush_chunk()
    
    # POST-PROCESS: Merge runts
    if len(chunks) > 1:
        merged: List[Chunk] = [chunks[0]]
        for ch in chunks[1:]:
            if ch.total_words < min_chunk_words and merged:
                prev = merged[-1]
                prev.elements.extend(ch.elements)
                prev.total_words += ch.total_words
                prev.estimated_minutes = round(prev.total_words / float(words_per_minute), 1)
            else:
                merged.append(ch)
                
        # Re-index
        for i, c in enumerate(merged):
            c.chunk_number = i + 1
            
        chunks = merged

    return chunks
