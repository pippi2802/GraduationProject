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

//ToggleFactory.MenuFactory - contains convenience methods to Radios and checkboxs
//(C)2000-2001 Mark Beynon
//mark@jpedit.co.uk
//http://www.jpedit.co.uk
package com.utils;

import java.awt.*;
import java.awt.event.*;

import javax.swing.*;

import com.jpe.jpe;
import com.jpe.Constants;

public class ToggleFactory implements Constants {
	public static JCheckBoxMenuItem createJCheckBoxMenuItem(String label,
			String tooltip, jpe win) {
		JCheckBoxMenuItem jcm = new JCheckBoxMenuItem(label);
		jcm.setToolTipText(tooltip);
		jcm.addActionListener(win);
		jcm.setFont(SYSTEM_FONT);
		return jcm;
	}

	// ****************************************************************************************
	public static JRadioButtonMenuItem createJRadButMenuItem(String label,
			boolean selected, jpe win) {
		JRadioButtonMenuItem radbut = new JRadioButtonMenuItem(label);
		if (selected) {
			radbut.setSelected(true);
		} else
			radbut.setSelected(false);

		radbut.addActionListener(win);
		radbut.setFont(SYSTEM_FONT);
		return radbut;
	}

}
