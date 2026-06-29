package edu.penn.rtg.schedulingapp.output;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;

import edu.penn.rtg.schedulingapp.TreeComponent;
import edu.penn.rtg.schedulingapp.SchedulingComponent;

/**
 * XMLOutput class handles saving the Analysis Output as an XML file
 */
public class XMLOutput {
	static public void writeOutput(TreeComponent rootComponent,
			String fileName, String algorithm) {
		File file = new File(fileName);
		FileOutputStream outStream;
		try {
			outStream = new FileOutputStream(file);
			writeOutput(outStream, rootComponent, "", algorithm);
			outStream.close();
		} catch (FileNotFoundException e) {
			System.err.println(e.getMessage());
			e.printStackTrace();
		} catch (IOException e) {
			System.err.println(e.getMessage());
			e.printStackTrace();
		}
	}

	static protected void writeOutput(FileOutputStream outStream,
			TreeComponent comp, String tabSpace, String algorithm) {
		String singleTabSpace = "\t";
		String[] multiLinesResource = comp.getResourceModelList().toString()
				.split("\n");
		String[] multiLinesTask = comp.getProcessedTaskList().toString().split(
				"\n");
		try {
			StringBuffer compDetails = new StringBuffer();
			compDetails.append(tabSpace + "<component name=\""
					+ comp.getCompName() + "\" algorithm=\"" + algorithm
					+ "\">\n");

			compDetails.append(tabSpace + singleTabSpace + "<resource>\n");
			for (String model : multiLinesResource) {
				String[] details = model.split(", ");
				compDetails.append(tabSpace + singleTabSpace + singleTabSpace
						+ "<model");
				for (String detail : details) {
					compDetails.append(" "
							+ getXMLString(detail.split(": ")[0]) + "=\"");
					compDetails.append(detail.split(": ")[1] + "\"");
				}
				compDetails.append("> </model>\n");
			}
			compDetails.append(tabSpace + singleTabSpace + "</resource>\n");

			compDetails
					.append(tabSpace + singleTabSpace + "<processed_task>\n");
			for (String model : multiLinesTask) {
				if(model.isEmpty())
					break;
				String[] details = model.split(", ");
				compDetails.append(tabSpace + singleTabSpace + singleTabSpace
						+ "<model");
				for (String detail : details) {
					compDetails.append(" "
							+ getXMLString(detail.split(": ")[0]) + "=\"");
					compDetails.append(detail.split(": ")[1] + "\"");
				}
				compDetails.append("> </model>\n");
			}
			compDetails.append(tabSpace + singleTabSpace
					+ "</processed_task>\n");
			outStream.write(compDetails.toString().getBytes());

			for (TreeComponent component : comp.getAllChildren()) {
				writeOutput(outStream, component, tabSpace + "\t", algorithm);
			}

			outStream.write(new String(tabSpace + "</component>\n").getBytes());
		} catch (FileNotFoundException e) {
			e.printStackTrace();
		} catch (IOException e) {
			e.printStackTrace();
		}
	}

	static protected String getXMLString(String parseString) {
		if (parseString.equals("Period")) {
			return "period";
		} else if (parseString.equals("Bandwidth")) {
			return "bandwidth";
		} else if (parseString.equals("Deadline")) {
			return "deadline";
		} else if (parseString.equals("Execution Time")) {
			return "execution_time";
		} else if (parseString.equals("Period2")) {
			return "period2";
		} else if (parseString.equals("Execution Time2")) {
			return "execution_time2";
		} else if (parseString.equals("Cpus")) {
			return "cpus";
		} else {
			return null;
		}
	}
}
