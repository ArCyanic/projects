TECTONIC ?= tectonic
GHOSTSCRIPT ?= gs
DRAWIO ?= /Applications/draw.io.app/Contents/MacOS/draw.io
BUILD_DIR := ../../build/paper-english
PDF := ../../output/pdf/dac-paper-en.pdf
FIGURES := $(BUILD_DIR)/motivation.pdf $(BUILD_DIR)/hardware.pdf $(BUILD_DIR)/framework.pdf
RAW_FIGURES := $(BUILD_DIR)/motivation.drawio.pdf $(BUILD_DIR)/hardware.drawio.pdf $(BUILD_DIR)/framework.drawio.pdf
PREVIEWS := figures/motivation.drawio.png figures/hardware.drawio.png figures/framework.drawio.png
SOURCES := dac-paper-en.tex sections/introduction.tex sections/background.tex sections/hardware.tex sections/methodology.tex sections/evaluation.tex tables/framework-comparison.tex tables/hardware-prototypes.tex references.bib
RESULT_FIGURES := $(addprefix $(BUILD_DIR)/,07-cross-model-results.pdf 04-main-results.pdf 05-capacity-mechanisms.pdf 06-scheduling-results.pdf)
.SECONDARY: $(RAW_FIGURES)
.PHONY: all
all: $(PDF) $(PREVIEWS)

$(PDF): $(SOURCES) $(FIGURES) $(RESULT_FIGURES) Makefile
	mkdir -p $(BUILD_DIR) ../../output/pdf
	$(TECTONIC) -X compile dac-paper-en.tex --outdir $(BUILD_DIR) --keep-logs
	cp $(BUILD_DIR)/dac-paper-en.pdf $(PDF)

$(BUILD_DIR)/%.drawio.pdf: figures/%.drawio Makefile
	mkdir -p $(BUILD_DIR)
	"$(DRAWIO)" -x -f pdf -e --crop -b 0 -o $@ $<

$(BUILD_DIR)/%.pdf: $(BUILD_DIR)/%.drawio.pdf
	$(GHOSTSCRIPT) -q -dBATCH -dNOPAUSE -sDEVICE=pdfwrite -dNoOutputFonts -dCompatibilityLevel=1.5 -sOutputFile=$@ $<

$(RESULT_FIGURES): $(BUILD_DIR)/%.pdf: ../figures/%.pdf Makefile
	mkdir -p $(BUILD_DIR)
	$(GHOSTSCRIPT) -q -dBATCH -dNOPAUSE -sDEVICE=pdfwrite -dNoOutputFonts -dCompatibilityLevel=1.5 -sOutputFile=$@ $<

figures/%.drawio.png: figures/%.drawio Makefile
	"$(DRAWIO)" -x -f png -e -s 3 -b 0 -o $@ $<

HARDWARE_PDF := ../../output/pdf/hardware-prototypes.pdf
HARDWARE_PNG := ../../output/pdf/hardware-prototypes.png

.PHONY: hardware-preview
hardware-preview: $(HARDWARE_PDF) $(HARDWARE_PNG)

$(HARDWARE_PDF): hardware-prototypes.tex tables/hardware-prototypes.tex references.bib Makefile
	mkdir -p $(BUILD_DIR) ../../output/pdf
	$(TECTONIC) -X compile hardware-prototypes.tex --outdir $(BUILD_DIR) --keep-logs
	cp $(BUILD_DIR)/hardware-prototypes.pdf $(HARDWARE_PDF)

$(HARDWARE_PNG): $(HARDWARE_PDF)
	pdftoppm -singlefile -f 1 -r 180 -png $< ../../output/pdf/hardware-prototypes
