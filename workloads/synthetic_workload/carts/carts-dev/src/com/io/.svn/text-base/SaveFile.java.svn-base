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

//class for saving files to different platforms
//(C)2000-2001 Mark Beynon
//mark@jpedit.co.uk
//http://www.jpedit.co.uk
package com.io;

import java.io.File;
import java.io.FileWriter;
import javax.swing.text.Document;
import javax.swing.text.Element;
import javax.swing.text.Segment;

import com.jpe.jpe;

public class SaveFile {

	public SaveFile(jpe win, String g, Document doc2) {
		super();
		this.win = win;
		run(g, doc2);
	}

	public void run(String g, Document doc2) {

		// this segment of code used with permission
		// (C)1999-2000 Romain Guy
		// Released under GPL-2 license (see LICENSE)
		// guy.romain@bigfoot.com
		// www.jext.org
		// *****************************************
		// *****************************************

		try {
			win.setWaitCursor();
			String newline = System.getProperty("line.separator");
			File file = new File(g);
			FileWriter out = new FileWriter(file);
			Segment lineSegment = new Segment();
			Element map = doc2.getDefaultRootElement();

			for (int i = 0; i < map.getElementCount(); i++) {
				Element line = map.getElement(i);
				int start = line.getStartOffset();
				doc2.getText(start, line.getEndOffset() - start - 1,
						lineSegment);
				out.write(lineSegment.array, lineSegment.offset,
						lineSegment.count);
				out.write(newline);
			}
			out.close();

			// *****************************************
			// *****************************************
		} catch (Exception e) {
		}

	}

	private jpe win;
}
