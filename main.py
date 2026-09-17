from privacy_service import initialize_analyzer, anonymize_and_store, restore_text

def simulate_llm(text: str) -> str:
    """Simulates sending the scrubbed text to ChatGPT."""
    return f"Rezumat generat de AI: Datele pentru {text} au fost procesate in siguranta."

def main():
    print("1. Booting up Presidio Analyzer...")
    analyzer = initialize_analyzer()
    
    test_text = (
        "Subsemnatul Popescu Ion, cetățean român, născut la data de 12.03.2005 în județul Constanța, localitatea Constanța," \
        "cu domiciliul în Str. Pacii nr. 4, bl. C4, sc. A, et. 2, ap. 12, având codul numeric personal 1900101123457, titular al C.I. seria KZ, nr. 688973," \
        "eliberat la data de 14.09.2026 de către SPCLEP Constanța." \
        ", număr de telefon 0745165009, email popescu.ion@spital.ro, cont bancar cu IBAN RO12 BTRL 1234 5678 9012 3456."
    )
    
    print("\n2. Executing Top Bread (Scrub & Store)...")
    safe_text, session_id = anonymize_and_store(test_text, analyzer)
    print(f"Session ID: {session_id}")
    print(f"Safe Text: {safe_text}")
    
    print("\n3. Sending to LLM...")
    llm_response = simulate_llm(safe_text)
    print(f"LLM Response: {llm_response}")
    
    print("\n4. Executing Bottom Bread (Restore)...")
    final_text = restore_text(llm_response, session_id)
    print(f"Final Restored Text: {final_text}")

if __name__ == "__main__":
    main()