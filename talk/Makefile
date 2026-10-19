TALK ?= talk
ENGINE ?= xelatex # Only `xelatex` or `lualatex` are allowed here

.PHONY: all clean dist-clean figures
.SUFFIXES: .pdf .tex

all: $(TALK).pdf

# Графики строятся из results/ скриптом analysis/talk_figures.py
figures:
	python3 ../analysis/talk_figures.py figures

%.pdf: %.tex *.tex figures/*.pdf
	latexmk -$(ENGINE) -synctex=1 -interaction=nonstopmode -file-line-error -shell-escape $<

clean:
	latexmk -c $(TALK).tex
	@$(RM) *.nav *.snm *.vrb *.synctex.gz

dist-clean: clean
	latexmk -C $(TALK).tex
