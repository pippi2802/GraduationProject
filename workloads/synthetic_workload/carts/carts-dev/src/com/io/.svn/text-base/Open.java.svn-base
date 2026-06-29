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

//class for opening of files on different platforms
//(C)2000-2001 Mark Beynon
//mark@jpedit.co.uk
//http://www.jpedit.co.uk
package com.io;

import com.utils.*;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;

import com.jpe.jpe;

public class Open {

	public Open(jpe win, String f, boolean r) {
		super();
		this.win = win;
		run(f, r);
	}

	public void run(String f, boolean r) {
		readonly = r;
		win.setWaitCursor();
		StringBuffer buffer;
		InputStreamReader in;
		// Open a file of the given name.

		File toLoad = new File(f);
		if ((!toLoad.exists()) || (!toLoad.canRead())) {
			Utils
					.userMessage(
							" Oops!",
							" File "
									+ f
									+ " no longer exists has been moved, or cannot be read from",
							2);

			win.setTextCursor();
			return;
		}

		else {
			if ((Utils.isReadOnly(f)) && (readonly)) {
				Utils.userMessage(" Read Only", " File " + f + " is Read Only",
						2);
			}
			try {
				// this segment ofcode used with permission
				// (C)1999-2000 Romain Guy
				// Released under GPL-2 license (see LICENSE)
				// guy.romain@bigfoot.com
				// www.jext.org
				// *****************************************
				// *****************************************

				buffer = new StringBuffer((int) toLoad.length());
				in = new InputStreamReader(new FileInputStream(toLoad));

				char[] buf = new char[BUFFER_SIZE];
				int len;
				boolean lastWasCR = false;

				// we read the file till its end (amazing, hu ?)
				while ((len = in.read(buf, 0, buf.length)) != -1) {
					int lastLine = 0;
					for (int i = 0; i < len; i++) {
						// ++count;
						switch (buf[i]) {
						// and we convert system's carriage return char into \n
						case '\r':
							if (lastWasCR) {
							} else
								lastWasCR = true;
							// if \r delete and replace with \n
							buffer.append(buf, lastLine, i - lastLine);
							buffer.append('\n');
							lastLine = i + 1;

							break;
						case '\n':
							if (lastWasCR) {
								lastWasCR = false;
								lastLine = i + 1;
							} else {
								buffer.append(buf, lastLine, i - lastLine);
								buffer.append('\n');
								lastLine = i + 1;
							}
							break;
						default:
							if (lastWasCR) {
								lastWasCR = false;
							}
							break;
						}
					}
				}
				in.close();
				in = null;

				// ********************************************
				// ********************************************

				if (buffer.length() != 0
						&& buffer.charAt(buffer.length() - 1) == '\n')
					buffer.setLength(buffer.length() - 1);

				// win.clearDoc();
				win.loadDoc(buffer.toString());
				win.setTextCursor();
				buffer = null;
			} catch (Exception e) {
			}
		}
	}

	private jpe win;
	boolean readonly;
	private static final int BUFFER_SIZE = 32768;

}
