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

//Intro.java - displays the splash screen and progress bar by calling a separate thread.
//Progress bar information is passed to the Intro by methods in the main program constructor
//(C)2000-2001 Mark Beynon
//mark@jpedit.co.uk
//http://www.jpedit.co.uk
package com.misc;

import java.awt.BorderLayout;
import java.awt.Font;
import java.awt.Color;

import javax.swing.JProgressBar;
import javax.swing.JPanel;
import javax.swing.JLabel;
import javax.swing.JWindow;
import javax.swing.ImageIcon;

import javax.swing.border.EtchedBorder;
import com.utils.*;

public class Intro extends JWindow implements Runnable {

	private JLabel label;
	private String fileSep = System.getProperty("file.separator");
	private Thread thread;
	private Utils Utils;
	private static JProgressBar progress;

	public Intro() {
		super();
		JPanel pane = new JPanel(new BorderLayout());
		JPanel progpane = new JPanel(new BorderLayout());
		label = new JLabel(new ImageIcon("images" + fileSep + "r.gif"));

		pane.add(label);

		progress = new JProgressBar(0, 100);
		progress.setStringPainted(true);
		progress.setForeground(Color.gray);
		progress.setBackground(Color.lightGray);
		progress.setFont(new Font("Arial", 0, 11));
		progress.setString("");

		progpane.add(progress);

		pane.setBorder(new EtchedBorder(EtchedBorder.RAISED));
		progpane.setBorder(new EtchedBorder(EtchedBorder.RAISED));

		getContentPane().setLayout(new BorderLayout());
		getContentPane().add(pane, BorderLayout.NORTH);
		getContentPane().add(progpane, BorderLayout.CENTER);

		pack();

		// this segment ofcode used with permission
		// (C)1999-2000 Romain Guy
		// Released under GPL-2 license (see LICENSE)
		// guy.romain@bigfoot.com
		// www.jext.org
		// *****************************************
		// *****************************************

		thread = new Thread(this);
		thread.setDaemon(true);
		thread.setPriority(Thread.NORM_PRIORITY);

		Utils.centerComponent(this);
		setVisible(true);
		this.requestFocus();

	}

	// *****************************************
	// *****************************************

	public void run() {
		thread.start();
	}

	public static void setProgText(String s) {
		progress.setString(s);
	}

	public static void setProg(int i) {
		progress.setValue(i);
	}

	public void hideSplash() {
		cancel();
	}

	void cancel() {
		thread.interrupt();
		thread = null;
		dispose();
	}
}
