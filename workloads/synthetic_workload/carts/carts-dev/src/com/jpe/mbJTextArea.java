/* This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

//mbJTextArea.java - extends the text component to provide extra functionality (append and insert)
//(C)2000-2001 Mark Beynon
//mark@jpedit.co.uk
//http://www.jpedit.co.uk
package com.jpe;

import javax.swing.JFrame;
import javax.swing.text.Document;
import javax.swing.text.BadLocationException;
import javax.swing.text.PlainDocument;
import com.textarea.*;

public class mbJTextArea extends JEditTextArea {

	private Find find;

	/**
	 * mbJTextArea constructor comment.
	 */
	public mbJTextArea(JFrame parent) {
		super();
		find = new Find(parent, this);
	}

	public mbJTextArea() {
		super();
	}

	public void append(String str) {
		Document doc = getDocument();
		if (doc != null) {
			try {
				doc.insertString(doc.getLength(), str, null);
			} catch (BadLocationException e) {
			}
		}
	}

	public void insert(String str, int pos) {
		Document doc = getDocument();
		if (doc != null) {
			try {
				doc.insertString(pos, str, null);
			} catch (BadLocationException e) {
				throw new IllegalArgumentException(e.getMessage());
			}
		}
	}

	public void setTabSize(int size) {
		Document doc = getDocument();
		if (doc != null) {
			int old = getTabSize();
			doc.putProperty(PlainDocument.tabSizeAttribute, new Integer(size));
			firePropertyChange("tabSize", old, size);
		}
	}

	public int getTabSize() {
		int size = 8;
		Document doc = getDocument();
		if (doc != null) {
			Integer i = (Integer) doc
					.getProperty(PlainDocument.tabSizeAttribute);
			if (i != null) {
				size = i.intValue();
			}
		}
		return size;
	}

	public Find getFind() {
		return find;
	}
}
