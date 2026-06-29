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

//class for providing file filtering for filechooser classes
//this code is used with permission
//(C)2000 Java Black book - Steven Holzner
//http://www.coriolis.com
package com.filefilters;

import java.io.File;

public class filterTypeJar extends javax.swing.filechooser.FileFilter {
	public boolean accept(File fileobj) {
		String extension = "";

		if (fileobj.isDirectory()) {
			return fileobj.isDirectory();
		} else {
			extension = fileobj.getPath().substring(
					fileobj.getPath().lastIndexOf('.') + 1).toLowerCase();
			return extension.equals("jar");
		}
	}

	public String getDescription() {
		return "Jar Files (*.jar)";
	}
}
