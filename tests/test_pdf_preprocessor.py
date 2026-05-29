from paper_writer_agent.pdf_preprocessor import PDFPreprocessor


def test_pdf_preprocessor_defaults_to_downsampled_images(tmp_path):
    preprocessor = PDFPreprocessor(tmp_path)

    assert preprocessor.image_zoom == 1.5
