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

package com.jpe;

import javax.swing.TransferHandler;
import javax.swing.JComponent;
import java.util.List;
import java.util.Arrays;
import java.io.File;
import java.io.IOException;
import java.awt.datatransfer.Transferable;
import java.awt.datatransfer.DataFlavor;
import java.awt.datatransfer.UnsupportedFlavorException;

import com.misc.*;
import com.utils.*;
import com.jpe.Constants;

class DropHandler extends TransferHandler {
	private jpe win;
	final static String SYSTEM_ERROR = new String(
			"An application error has occured, please see error log. Tools > Error log");

	DropHandler(jpe win) {
		this.win = win;
	}

	public boolean importData(JComponent component, Transferable transferable) {
		if (!canImport(component, transferable.getTransferDataFlavors())) {
			return false;
		} else {
			try {
				importFiles(transferable);
				return true;
			} catch (UnsupportedFlavorException e) {
				// win.setText(e.getMessage());
				System.out.println("Error dropping file " + e.getMessage());
				Utils.userMessage("Error", SYSTEM_ERROR, 1);
				Utils.writeErrorLog("Error dropping file  " + e.getMessage());
			} catch (IOException e) {
				// win.setText(e.getMessage());
				System.out.println("IO Error dropping file " + e.getMessage());
				Utils.userMessage("Error", SYSTEM_ERROR, 1);
				Utils
						.writeErrorLog("IO Error dropping file  "
								+ e.getMessage());
			}
			return false;
		}
	}

	private void importFiles(Transferable transferable)
			throws UnsupportedFlavorException, IOException {
		List files = (List) transferable
				.getTransferData(DataFlavor.javaFileListFlavor);
		for (int i = 0; i < files.size(); i++) {
			win.open(files.get(i).toString());
		}
	}

	public boolean canImport(JComponent c, DataFlavor[] flavors) {
		return Arrays.asList(flavors).contains(DataFlavor.javaFileListFlavor);
	}
}
