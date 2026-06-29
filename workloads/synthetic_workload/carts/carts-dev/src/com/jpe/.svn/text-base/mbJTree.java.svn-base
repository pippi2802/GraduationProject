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

import java.io.File;
import javax.swing.JTree;
import java.util.Hashtable;

public class mbJTree extends JTree {
	/**
	 * mbJTextArea constructor comment.
	 */
	public mbJTree() {
		super();

	}

	public mbJTree(boolean fullpath) {
		super();
		this.fullpath = fullpath;
	}

	public mbJTree(Hashtable h) {
		super();
	}

	public String convertValueToText(Object value, boolean selected,
			boolean expanded, boolean leaf, int row, boolean hasFocus) {
		if (value != null)
			if (fullpath) {
				return value.toString();
			} else {
				return new File(value.toString()).getName().toString();
			}

		return "";
	}
	boolean fullpath;
}
