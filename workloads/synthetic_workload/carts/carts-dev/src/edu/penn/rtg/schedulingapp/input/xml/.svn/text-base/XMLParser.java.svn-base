package edu.penn.rtg.schedulingapp.input.xml;

import javax.xml.parsers.DocumentBuilderFactory;
import java.io.FileReader;
import java.io.Reader;
import org.w3c.dom.Document;
import org.xml.sax.InputSource;

/**
 * Interprets an XML document via and stores all informations contained within
 * in a DOM (Document Object Model) Scheduling tree object.
 */

public class XMLParser {

	Document doc;

	/**
	 * Takes a filename as a string and attempts to parse the specified file
	 * 
	 * @param filename
	 *            - the name of the file (the full filepath)
	 * @throws java.lang.Exception
	 */
	public XMLParser(String filename) throws Exception {
		doc=DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(filename);
	}

	/**
	 * return document
	 * 
	 * @return document
	 */

	public Document getDocument() {
		return doc;
	}
}
