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

// About.class - displays an about box. A JLabel is used to display the start up splash screen.
//The JLabel is registered as a mouse listener and disapears when the user clicks on it.
//(C)2000-2001 Mark Beynon
//mark@jpedit.co.uk
//http://www.jpedit.co.uk
package com.misc;

import java.awt.event.MouseListener;
import java.awt.event.MouseEvent;
import java.awt.event.InputEvent;
import javax.swing.JLabel;
import javax.swing.JWindow;
import javax.swing.border.EtchedBorder;
import javax.swing.ImageIcon;
import com.utils.*;

public class About extends JWindow implements MouseListener {

	private JLabel label;
	private String fileSep = System.getProperty("file.separator");
	private Utils Utils;

	public About() {
		super();
		label = new JLabel(new ImageIcon("images" + fileSep + "r.gif"));
		label.setBorder(new EtchedBorder(EtchedBorder.RAISED));

		getContentPane().add(label);
		pack();

		label.addMouseListener(this);
		Utils.centerComponent(this);
		setVisible(true);
	}

	// mouse event
	public void mousePressed(MouseEvent e) {
		if ((e.getModifiers() & InputEvent.BUTTON1_MASK) == InputEvent.BUTTON1_MASK)
			cancel();

		else if ((e.getModifiers() & InputEvent.BUTTON3_MASK) == InputEvent.BUTTON3_MASK)
			cancel();
	}

	public void mouseClicked(MouseEvent e) {
	}

	public void mouseReleased(MouseEvent e) {
	}

	public void mouseEntered(MouseEvent e) {
	}

	public void mouseExited(MouseEvent e) {
	}

	void cancel() {
		dispose();
	}
}
