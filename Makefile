

default: build

NBNAME=dicts_and_dataframes
IPYNB=${NBNAME}.ipynb
NBMD=${NBNAME}.md

build-nbconvert:
	jupyter-nbconvert ${IPYNB} --to markdown --execute
	${MAKE} cleanup-md

cleanup-nbconvert-sed:
	cat ${NBNAME}.md | tr '\n' 'Õ' > ${NBMD}.md
	$(shell sed -i 's/<!-.*->Õ//g' ${NBMD}.md)
	$(shell sed -i 's/ÕÕÕ/Õ/g' ${NBMD}.md)
	$(shell sed -i 's/ÕÕ/Õ/g' ${NBMD}.md)
	$(shell sed -i 's/```ÕÕ/```Õ/g' ${NBMD}.md)
	cat ${NBMD}.md | tr 'Õ' '\n' > ${NBMD}

cleanup-md:
	python ./cleanupmd.py ${NBMD}

less-md:
	lessv ${NBNAME}.md

build-jupytext:
	jupytext ${IPYNB} --to markdown --execute

markdownfmt=gfm
markdownfmt=markdown
markdownfmt=commonmark
build-nbconvert-pandoc:
	jupyter-nbconvert ${IPYNB} --to html --execute
	pandoc --from html --to ${markdownfmt} ${NBNAME}.html  -o ${NBNAME}.html.md
