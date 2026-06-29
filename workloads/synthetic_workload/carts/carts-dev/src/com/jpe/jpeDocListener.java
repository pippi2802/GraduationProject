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

//this class listens for changes to the document associated with the text component and calls one
// of three methods depending on the changes made.
//(C)2000-2001 Mark Beynon
//mark@jpedit.co.uk
//http://www.jpedit.co.uk
package com.jpe;

import javax.swing.event.DocumentEvent;

class jpeDocListener implements javax.swing.event.DocumentListener {
	jpe win;

	jpeDocListener(jpe win) {
		this.win = win;
	}

	public void changedUpdate(DocumentEvent e) {
		win.doc_changed(e);
	}

	public void insertUpdate(DocumentEvent e) {
		win.doc_insert(e);
	}

	public void removeUpdate(DocumentEvent e) {
		win.doc_remove(e);
	}
}
