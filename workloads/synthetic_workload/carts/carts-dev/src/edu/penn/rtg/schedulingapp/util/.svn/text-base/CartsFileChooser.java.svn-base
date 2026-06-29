package edu.penn.rtg.schedulingapp.util;

import java.awt.Font;
import java.io.File;

import javax.swing.JFileChooser;
import javax.swing.JFrame;
import javax.swing.filechooser.FileFilter;

public class CartsFileChooser {
	public static File[] openFile(JFrame frame,File curDir,int limit)
	{
		File f[] = new File[limit];
		JFileChooser jFileChooser=new JFileChooser();
		jFileChooser.setCurrentDirectory(curDir);
		jFileChooser.setMultiSelectionEnabled(true);
		jFileChooser.setFont(new Font("Arial", 0, 11));

		class MyFileFilter extends FileFilter {
			@Override
			public boolean accept(File arg0) {
				String fileName = arg0.getName();
				if (arg0.isDirectory()) {
					return true;
				}
				if (fileName.endsWith(".xml")) {
					return true;
				}
				return false;
			}

			@Override
			public String getDescription() {
				return "xml";
			}
		}
		jFileChooser.setFileFilter(new MyFileFilter());
		if (jFileChooser.showOpenDialog(frame) == JFileChooser.APPROVE_OPTION) {
			f = jFileChooser.getSelectedFiles();

			if (f.length < limit) {
				return f;
			}
			UserUtil.show("File limit reached",
					"File opening limit of 99 exceeded!");
		}
		return null;
	
	}

	public static File saveFile(JFrame frame,File curDir,String targetFileName) {
		JFileChooser jFileChooser=new JFileChooser();
		jFileChooser.setCurrentDirectory(curDir);
		jFileChooser.setDialogTitle("Save " + targetFileName + " As");
		jFileChooser.setApproveButtonText("Save");
		jFileChooser.setSelectedFile(new File(targetFileName));
		jFileChooser.setFont(new Font("Arial", 0, 11));

		if (JFileChooser.APPROVE_OPTION == jFileChooser.showSaveDialog(frame)) {
			return jFileChooser.getSelectedFile();
		}
		return null;
	}
}
